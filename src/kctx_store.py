"""Кластерный журнал для `:kctx` — история наборов переменных kubectl-стека.

Когда известен текущий кластер kubectl (вход через ``klogin X``,
``tsh kube login X`` или ``kubectl config use-context X``), присваивания
переменных стека (`$NS=…`, `$POD=…`) сохраняются в отдельный файл
data-каталога — не в БД тегов и не в историю.

Файл: список снимков ``[{"cluster": str, "ts": float, "vars": {…}}]``.
``vars`` — только переменные kubectl-стека (``KUBE_STACK_VARS``).
Записи под portalocker-локом, как ``history_store``; идентичный последний
снимок кластера не дублируется (обновляется время). Модуль без Textual.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping

from history_store import (
    FileLockTimeoutError,
    acquire_file_lock,
    release_file_lock,
)

# Переменные, которыми живут шаблоны kubectl (src/seed_k8s_chains.py).
KUBE_STACK_VARS = ("NS", "POD", "DEPLOY", "SVC", "ING", "APP", "CTR", "QUOTA")
KUBE_STACK_VAR_NAMES = frozenset(KUBE_STACK_VARS)

ENCODING = "utf-8"
DEFAULT_LOCK_TIMEOUT = 5
DEFAULT_PER_CLUSTER_LIMIT = 20
DEFAULT_TOTAL_LIMIT = 200

# Вход в кластер: alias `klogin <cluster>`, `tsh kube login <cluster>` или
# `kubectl config use-context <context>` (когда tsh недоступен).
RE_KUBE_LOGIN = re.compile(
    r"^(?:klogin|tsh\s+kube\s+login|kubectl\s+config\s+use-context)\s+([^\s;&|]+)"
)


def parse_cluster_login(text: str) -> str | None:
    """Имя кластера из строки входа: `klogin prod`, `tsh kube login prod`,
    `kubectl config use-context prod`."""
    needle = (text or "").strip()
    if not needle:
        return None
    match = RE_KUBE_LOGIN.match(needle)
    return match.group(1).strip() if match else None


def stack_vars(env: Mapping[str, str]) -> dict[str, str]:
    """Подмножество env только из kubectl-стека (непустые значения)."""
    result: dict[str, str] = {}
    for key in KUBE_STACK_VARS:
        value = env.get(key)
        if value is not None and str(value).strip() != "":
            result[key] = str(value)
    return result


def _parse_items(raw: str) -> list[dict]:
    """Список снимков из JSON-текста. Мусор/пусто → []."""
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    items: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        cluster = entry.get("cluster")
        ts = entry.get("ts")
        vars_map = entry.get("vars")
        if not (
            isinstance(cluster, str)
            and cluster.strip()
            and isinstance(ts, (int, float))
            and isinstance(vars_map, dict)
        ):
            continue
        clean_vars = {
            str(key): str(value)
            for key, value in vars_map.items()
            if str(value).strip() != ""
        }
        items.append(
            {"cluster": cluster.strip(), "ts": float(ts), "vars": clean_vars}
        )
    return items


def load_snapshots(path: str) -> list[dict]:
    """Читает журнал (shared-lock, если доступен). Нет файла/ошибки → []."""
    try:
        f = open(path, encoding=ENCODING)
    except OSError:
        return []
    with f:
        locked = False
        try:
            acquire_file_lock(f, timeout_sec=0, shared=True)
            locked = True
        except (OSError, FileLockTimeoutError):
            locked = False
        try:
            return _parse_items(f.read())
        finally:
            if locked:
                release_file_lock(f)


def _trim(
    items: list[dict],
    per_cluster_limit: int,
    total_limit: int,
) -> list[dict]:
    """Оставляет свежайшие снимки: per_cluster_limit на кластер, total_limit всего."""
    if per_cluster_limit <= 0 and total_limit <= 0:
        return []
    by_cluster: dict[str, list[dict]] = {}
    for item in items:
        by_cluster.setdefault(item["cluster"], []).append(item)
    kept: list[dict] = []
    for cluster_items in by_cluster.values():
        cluster_items.sort(key=lambda item: item["ts"], reverse=True)
        kept.extend(cluster_items[: max(1, per_cluster_limit)])
    kept.sort(key=lambda item: item["ts"], reverse=True)
    if total_limit > 0:
        kept = kept[:total_limit]
    return kept


def add_snapshot(
    path: str,
    cluster: str,
    env: Mapping[str, str],
    *,
    now: float | None = None,
    per_cluster_limit: int = DEFAULT_PER_CLUSTER_LIMIT,
    total_limit: int = DEFAULT_TOTAL_LIMIT,
    lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> bool:
    """Сохраняет снимок kubectl-стека для кластера.

    Возвращает True, если файл изменился. Идентичный последнему снимку того
    же кластера набор не дублируется — обновляется только время. Пустой
    стек/нет кластера → False без записи. При конфликте лока или ошибке
    записи — False (присваивание переменной работает как раньше).
    """
    name = (cluster or "").strip()
    snapshot_vars = stack_vars(env)
    if not name or not snapshot_vars:
        return False
    ts = time.time() if now is None else float(now)

    try:
        with open(path, "a+", encoding=ENCODING) as f:
            locked = False
            try:
                acquire_file_lock(f, lock_timeout)
                locked = True
            except (OSError, FileLockTimeoutError):
                return False
            try:
                f.seek(0)
                items = _parse_items(f.read())
                candidate = {"cluster": name, "ts": ts, "vars": snapshot_vars}

                # Последний снимок этого кластера с тем же набором — только bump.
                last_index = -1
                for i in range(len(items) - 1, -1, -1):
                    if items[i]["cluster"] == name:
                        last_index = i
                        break
                if last_index >= 0 and items[last_index]["vars"] == snapshot_vars:
                    items[last_index]["ts"] = ts
                else:
                    items.append(candidate)

                kept = _trim(items, per_cluster_limit, total_limit)
                f.seek(0)
                f.truncate()
                json.dump(kept, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                return True
            finally:
                if locked:
                    release_file_lock(f)
    except OSError:
        return False


def snapshots_for_cluster(items: list[dict], cluster: str) -> list[dict]:
    """Снимки кластера, свежайшие сверху."""
    name = (cluster or "").strip()
    picked = [item for item in items if item.get("cluster") == name]
    picked.sort(key=lambda item: item.get("ts", 0.0), reverse=True)
    return picked


def cluster_summary(items: list[dict]) -> list[dict]:
    """Кластеры из журнала: {cluster, count, last_ts}, свежайшие сверху."""
    by_cluster: dict[str, list[dict]] = {}
    for item in items:
        name = item.get("cluster")
        if name:
            by_cluster.setdefault(name, []).append(item)
    summary = [
        {
            "cluster": name,
            "count": len(entries),
            "last_ts": max(float(entry.get("ts", 0.0)) for entry in entries),
        }
        for name, entries in by_cluster.items()
    ]
    summary.sort(key=lambda item: item["last_ts"], reverse=True)
    return summary


def format_vars(vars_map: Mapping[str, str]) -> str:
    """`NS=team-a POD=api-7f` — для списков журнала."""
    parts: list[str] = []
    for key in KUBE_STACK_VARS:
        value = vars_map.get(key)
        if value is not None and str(value).strip() != "":
            parts.append(f"{key}={value}")
    return " ".join(parts)
