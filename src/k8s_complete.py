"""Дополнение имён ресурсов Kubernetes из живого кластера.

Используется автодополнением TUI только для контекста ``kubectl get <res> …``
и при включённом флаге ``k8s_completion: true`` в settings.yml.

Здесь нет тяжёлых зависимостей: просто ``kubectl get <resource> -o name``
с коротким таймаутом и мягким fallback — если kubectl не настроен или
кластер недоступен, возвращается ``None`` (контекст не распознан) или ``[]``
(контекст распознан, но имён нет / kubectl упал).
"""
import subprocess

# Словарь синонимов ресурса → имя ресурса для `kubectl get`.
RESOURCE_ALIASES = {
    "pod": "pods",
    "pods": "pods",
    "po": "pods",
    "svc": "services",
    "service": "services",
    "services": "services",
    "deploy": "deployments",
    "deployment": "deployments",
    "deployments": "deployments",
    "ing": "ingresses",
    "ingress": "ingresses",
    "ingresses": "ingresses",
    "cm": "configmaps",
    "configmap": "configmaps",
    "configmaps": "configmaps",
    "secret": "secrets",
    "secrets": "secrets",
    "ns": "namespaces",
    "namespace": "namespaces",
    "namespaces": "namespaces",
    "node": "nodes",
    "nodes": "nodes",
    "pvc": "persistentvolumeclaims",
    "sts": "statefulsets",
    "statefulset": "statefulsets",
    "statefulsets": "statefulsets",
    "ds": "daemonsets",
    "daemonset": "daemonsets",
    "daemonsets": "daemonsets",
    "job": "jobs",
    "jobs": "jobs",
    "cronjob": "cronjobs",
    "cronjobs": "cronjobs",
}


def parse_kubectl_get_context(text: str):
    """(resource, namespace, prefix) для ``kubectl get <res> [flags] <prefix>``.

    Возвращает None, если это не похоже на `kubectl get …` (тогда обычное
    автодополнение работает как раньше).
    """
    tokens = (text or "").split()
    if not tokens or tokens[0] != "kubectl":
        return None
    try:
        get_idx = tokens.index("get")
    except ValueError:
        return None
    if get_idx + 1 >= len(tokens):
        return None
    resource_token = tokens[get_idx + 1]
    resource = RESOURCE_ALIASES.get(resource_token)
    if resource is None:
        return None

    namespace = None
    prefix = ""
    i = get_idx + 2
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-n", "--namespace"):
            if i + 1 < len(tokens):
                namespace = tokens[i + 1]
            i += 2
            continue
        if tok in ("-A", "--all-namespaces"):
            namespace = ""  # пусто = все namespace
            i += 1
            continue
        if tok.startswith("-"):
            i += 1
            continue
        prefix = tok
        i += 1
    return resource, namespace, prefix


def _run_kubectl(resource: str, namespace: str | None, timeout: float) -> list[str]:
    """`kubectl get <resource> -o name` → список строк `<kind>/<name>`."""
    args = ["kubectl", "get", resource, "-o", "name"]
    if namespace == "":
        args.append("-A")
    elif namespace:
        args += ["-n", namespace]
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        return []
    return completed.stdout.splitlines()


def kubectl_resource_candidates(text: str, timeout: float = 1.5) -> list[str] | None:
    """Имена ресурсов для текущего kubectl-контекста.

    None — текст не является `kubectl get …` (не трогать обычное дополнение);
    список — имена ресурсов, отфильтрованные по префиксу (может быть пустым).
    """
    ctx = parse_kubectl_get_context(text)
    if ctx is None:
        return None
    resource, namespace, prefix = ctx
    try:
        lines = _run_kubectl(resource, namespace, timeout)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return []
    names: list[str] = []
    for line in lines:
        name = line.split("/", 1)[-1].strip()
        if not name:
            continue
        if prefix and not name.startswith(prefix):
            continue
        names.append(name)
    names = sorted(set(names))
    return names[:50]
