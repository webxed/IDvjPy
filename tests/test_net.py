"""Сетевой слой (`src/net.py`): прокси с логином и подсказка при 407."""
import urllib.error
from urllib.request import Request

import pytest

import cheat_sh
import llm_client
import net
from net import (
    PROXY_AUTH_HINT,
    SchemeCheckingRedirectHandler,
    allowed_redirect_schemes,
    format_fetch_error,
    inject_proxy_userinfo,
    looks_like_proxy_auth_error,
    open_url,
    proxy_handler_map,
    redact_proxy_secrets,
)


def test_allowed_redirect_schemes_never_downgrade_to_http():
    """`https → http` — не переход: содержимое ехало бы открытым текстом."""
    assert allowed_redirect_schemes("https") == frozenset({"https"})
    assert allowed_redirect_schemes("http") == frozenset({"http", "https"})
    # `:import --insecure` — явный выбор пользователя, http-переход разрешён.
    assert allowed_redirect_schemes("https", ("http",)) == frozenset({"http", "https"})


class _FakeFp:
    """Заглушка файлового объекта для `redirect_request`."""

    def close(self) -> None:
        pass


def _redirect(handler: SchemeCheckingRedirectHandler, url: str):
    request = Request("https://host/tags.json")
    return handler.redirect_request(request, _FakeFp(), 302, "Found", {}, url)


def test_redirect_handler_refuses_http_hop():
    handler = SchemeCheckingRedirectHandler(allowed_redirect_schemes("https"))
    with pytest.raises(urllib.error.HTTPError):
        _redirect(handler, "http://mirror/tags.json")
    assert _redirect(handler, "https://host/other.json") is not None


def test_open_url_installs_scheme_guard(monkeypatch):
    captured = {}

    class _Opener:
        def open(self, request, timeout=None):
            return "ok"

    def fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return _Opener()

    monkeypatch.setattr(net.urllib.request, "build_opener", fake_build_opener)
    assert open_url(Request("https://host/x"), 1.0, {}) == "ok"
    guards = [
        handler
        for handler in captured["handlers"]
        if isinstance(handler, SchemeCheckingRedirectHandler)
    ]
    assert guards and guards[0].allowed == frozenset({"https"})


def test_all_outbound_calls_share_the_guarded_transport(monkeypatch):
    """`:llm` и `:cht` ходят через `net.open_url`, а не своим urlopen.

    Своя копия транспорта обошла бы redirect-guard: ключ API мог бы уехать
    по `https → http`.
    """
    seen = []

    def fake_open(request, timeout, environ, **kwargs):
        seen.append((request.full_url, timeout))
        return "ok"

    monkeypatch.setattr(net, "open_url", fake_open)
    request = Request("https://api.example/x")
    assert llm_client._open_request(request, 5.0, {"K": "v"}) == "ok"
    assert cheat_sh._open(request, 5.0, {"K": "v"}) == "ok"
    assert seen == [("https://api.example/x", 5.0)] * 2


def test_inject_proxy_userinfo():
    assert inject_proxy_userinfo("http://proxy.corp:8080", "alice", "s3cret") == (
        "http://alice:s3cret@proxy.corp:8080"
    )
    assert inject_proxy_userinfo("http://proxy.corp:8080", "alice", "p@ss:word") == (
        "http://alice:p%40ss%3Aword@proxy.corp:8080"
    )
    assert inject_proxy_userinfo("http://old:pw@proxy.corp:8080", "alice", "x") == (
        "http://old:pw@proxy.corp:8080"
    )
    assert inject_proxy_userinfo("http://proxy.corp:8080", "", "x") == "http://proxy.corp:8080"
    assert inject_proxy_userinfo("proxy.corp:8080", "alice", "x") == (
        "http://alice:x@proxy.corp:8080"
    )


def test_proxy_handler_map_injects_when_user_set():
    env = {
        "HTTPS_PROXY": "http://proxy.example:3128",
        "PROXY_USER": "alice",
        "PROXY_PASS": "s3cret",
    }
    mapping = proxy_handler_map(env)
    assert mapping is not None
    assert mapping["https"] == "http://alice:s3cret@proxy.example:3128"
    assert "http" not in mapping
    only_http = proxy_handler_map(
        {
            "HTTP_PROXY": "http://proxy.example:3128",
            "PROXY_USER": "alice",
            "PROXY_PASS": "s3cret",
        }
    )
    assert only_http is not None
    assert only_http["https"] == "http://alice:s3cret@proxy.example:3128"
    assert only_http["http"] == "http://alice:s3cret@proxy.example:3128"
    assert proxy_handler_map({"HTTPS_PROXY": "http://proxy.example:3128"}) is None
    assert proxy_handler_map({"PROXY_USER": "alice"}) is None


def test_redact_proxy_secrets():
    env = {"PROXY_PASS": "s3cret"}
    assert "***" in redact_proxy_secrets("tunnel s3cret failed", env)
    assert "s3cret" not in redact_proxy_secrets("tunnel s3cret failed", env)
    env = {"PROXY_PASS": "p@ss"}
    text = redact_proxy_secrets("http://alice:p%40ss@proxy:1 407", env)
    assert "p@ss" not in text
    assert "p%40ss" not in text


def test_looks_like_proxy_auth_error():
    assert looks_like_proxy_auth_error("407 Proxy Authentication Required")
    assert not looks_like_proxy_auth_error("timed out")


def test_format_fetch_error_hint_only_without_user():
    err = OSError("407 Proxy Authentication Required")
    with_hint = format_fetch_error(err, {"HTTPS_PROXY": "http://proxy:8080"}, subject="Fetch")
    assert "Fetch:" in with_hint and PROXY_AUTH_HINT in with_hint
    without = format_fetch_error(err, {"PROXY_USER": "alice"}, subject="Fetch")
    assert PROXY_AUTH_HINT not in without
    timeout = format_fetch_error(TimeoutError("timed out"), {}, subject="Fetch")
    assert "timed out" in timeout and PROXY_AUTH_HINT not in timeout
    # Пароль прокси не светится в сообщении.
    leak = format_fetch_error(OSError("bad p@ss"), {"PROXY_PASS": "p@ss"}, subject="Fetch")
    assert "p@ss" not in leak and "***" in leak
