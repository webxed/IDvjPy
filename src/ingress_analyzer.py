"""
Модуль анализа Kubernetes Ingress.

Инструменты для разбора конфигураций Kubernetes ingress,
парсинга конфигов nginx через crossplane и отладки проблем маршрутизации.
"""

import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class IngressInfo:
    """Представляет ресурс Kubernetes Ingress."""
    name: str
    namespace: str
    hosts: list[str]
    paths: list[dict[str, str]]
    services: list[dict[str, Any]]
    annotations: dict[str, str] = field(default_factory=dict)
    tls: list[dict[str, str]] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict, repr=False)


@dataclass
class NginxLocation:
    """Представляет разобранный блок location nginx."""
    path: str
    modifier: str | None = None  # =, ~, ~*, ^~
    proxy_pass: str | None = None
    upstream: str | None = None
    rewrite_rules: list[dict] = field(default_factory=list)
    raw_directives: list[dict] = field(default_factory=list)


@dataclass
class UpstreamInfo:
    """Представляет блок upstream nginx."""
    name: str
    servers: list[str] = field(default_factory=list)
    port: int | None = None
    raw_directives: list[dict] = field(default_factory=list)


@dataclass
class EndpointInfo:
    """Представляет endpoint Kubernetes."""
    ip: str
    port: int
    ready: bool = True
    pod_name: str | None = None


@dataclass
class ServiceInfo:
    """Представляет сервис Kubernetes с endpoint'ами."""
    name: str
    namespace: str
    type: str
    ports: list[dict]
    selector: dict[str, str]
    endpoints: list[EndpointInfo] = field(default_factory=list)
    healthy_endpoints: int = 0
    total_endpoints: int = 0


class IngressAnalyzerError(Exception):
    """Базовое исключение для IngressAnalyzer."""
    pass


class CrossplaneNotInstalledError(IngressAnalyzerError):
    """Возбуждается, когда crossplane не установлен."""
    pass


class KubectlError(IngressAnalyzerError):
    """Возбуждается, когда команда kubectl завершилась ошибкой."""
    pass


class IngressAnalyzer:
    """
    Основной класс для анализа Kubernetes ingress.

    Использование:
        analyzer = IngressAnalyzer()
        ingresses = analyzer.list_ingresses()
        result = analyzer.analyze_ingress("my-ingress", "default")
    """

    # Частые метки nginx ingress controller
    INGRESS_CONTROLLER_LABELS = [
        "app.kubernetes.io/component=controller",
        "app=nginx-ingress",
        "app=ingress-nginx",
        "name=ingress-nginx",
        "app.kubernetes.io/name=ingress-nginx",
    ]

    # Частые namespace для ingress controller
    INGRESS_CONTROLLER_NAMESPACES = [
        "ingress-nginx",
        "kube-system",
        "nginx-ingress",
    ]

    def __init__(self, timeout: int = 30, default_namespace: str = "default"):
        self.timeout = timeout
        self.default_namespace = default_namespace
        self._crossplane_available: bool | None = None
        self._cached_controller: tuple[str, str] | None = None

    def _run_kubectl(self, args: list[str], namespace: str | None = None,
                     json_output: bool = True) -> tuple[int, str, str]:
        """
        Запускает kubectl и возвращает (returncode, stdout, stderr).

        Аргументы:
            args: аргументы kubectl (без 'kubectl')
            namespace: используемый namespace (необязательно, добавляет флаг -n)
            json_output: добавить флаг -o json

        Возвращает:
            Кортеж (returncode, stdout, stderr)
        """
        cmd = ["kubectl"]
        if namespace:
            cmd.extend(["-n", namespace])
        if json_output:
            cmd.append("-o")
            cmd.append("json")
        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                # Клавиатура TUI не для детей: kubectl не читает stdin.
                stdin=subprocess.DEVNULL,
                timeout=self.timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            raise KubectlError(f"kubectl command timed out after {self.timeout}s") from None
        except FileNotFoundError:
            raise KubectlError("kubectl not found. Please install kubectl.") from None

    def check_crossplane(self) -> tuple[bool, str]:
        """
        Проверяет, установлен ли crossplane и доступен ли он.

        Возвращает:
            Кортеж (is_available, version_or_error)
        """
        if self._crossplane_available is not None:
            return self._crossplane_available, ""

        try:
            result = subprocess.run(
                ["crossplane", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self._crossplane_available = True
                return True, result.stdout.strip()
            return False, "crossplane not found"
        except FileNotFoundError:
            self._crossplane_available = False
            return False, "crossplane not installed. Run: pip install crossplane"
        except subprocess.TimeoutExpired:
            return False, "crossplane check timed out"


    def list_ingresses(self, namespace: str | None = None) -> list[IngressInfo]:
        """
        Получает список ingress.

        Аргументы:
            namespace: конкретный namespace или None для всех namespace

        Возвращает:
            Список объектов IngressInfo

        Исключения:
            KubectlError: если команда kubectl завершилась ошибкой
        """
        if namespace:
            returncode, stdout, stderr = self._run_kubectl(
                ["get", "ingress"],
                namespace=namespace,
                json_output=True
            )
        else:
            returncode, stdout, stderr = self._run_kubectl(
                ["get", "ingress", "--all-namespaces"],
                json_output=True
            )

        if returncode != 0:
            raise KubectlError(f"Failed to list ingresses: {stderr}")

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            raise KubectlError("Failed to parse kubectl output") from None

        ingresses = []
        for item in data.get("items", []):
            ingress = self._parse_ingress_item(item)
            if ingress:
                ingresses.append(ingress)

        return ingresses

    def _parse_ingress_item(self, item: dict) -> IngressInfo | None:
        """Разбирает один элемент ingress из вывода kubectl."""
        try:
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})

            name = metadata.get("name", "")
            namespace = metadata.get("namespace", self.default_namespace)
            annotations = metadata.get("annotations", {})

            # Извлечь хосты
            hosts = []
            tls = spec.get("tls", [])
            for tls_entry in tls:
                for host in tls_entry.get("hosts", []):
                    if host not in hosts:
                        hosts.append(host)

            # Извлечь пути и сервисы из правил
            paths = []
            services = []
            rules = spec.get("rules", [])

            for rule in rules:
                host = rule.get("host", "*")
                if host not in hosts:
                    hosts.append(host)

                http = rule.get("http", {})
                for path_entry in http.get("paths", []):
                    path_info = {
                        "path": path_entry.get("path", "/"),
                        "pathType": path_entry.get("pathType", "Prefix"),
                        "host": host,
                    }

                    backend = path_entry.get("backend", {})
                    service = backend.get("service", {})

                    if service:
                        path_info["serviceName"] = service.get("name", "")
                        path_info["servicePort"] = service.get("port", {}).get(
                            "number", service.get("port", {}).get("name", "")
                        )

                        # Отследить уникальные сервисы
                        svc_name = service.get("name", "")
                        if svc_name and not any(s.get("name") == svc_name for s in services):
                            services.append({
                                "name": svc_name,
                                "port": path_info["servicePort"],
                                "namespace": namespace,
                            })

                    paths.append(path_info)

            # Обработать default backend
            default_backend = spec.get("defaultBackend", {}).get("service", {})
            if default_backend:
                svc_name = default_backend.get("name", "")
                if svc_name and not any(s.get("name") == svc_name for s in services):
                    services.append({
                        "name": svc_name,
                        "port": default_backend.get("port", {}).get("number", ""),
                        "namespace": namespace,
                    })

            return IngressInfo(
                name=name,
                namespace=namespace,
                hosts=hosts,
                paths=paths,
                services=services,
                annotations=annotations,
                tls=tls,
                raw_json=item
            )

        except Exception as e:
            print(f"Error parsing ingress item: {e}")
            return None

    def get_ingress(self, name: str, namespace: str | None = None) -> IngressInfo | None:
        """
        Получает детали конкретного ingress.

        Аргументы:
            name: имя ingress
            namespace: namespace (по умолчанию используется default)

        Возвращает:
            IngressInfo или None, если не найдено
        """
        ns = namespace or self.default_namespace
        returncode, stdout, stderr = self._run_kubectl(
            ["get", "ingress", name],
            namespace=ns,
            json_output=True
        )

        if returncode != 0:
            return None

        try:
            data = json.loads(stdout)
            return self._parse_ingress_item(data)
        except json.JSONDecodeError:
            return None

    def find_ingress_controller_pod(self) -> tuple[str | None, str | None]:
        """
        Находит имя пода nginx ingress controller и его namespace.

        Возвращает:
            Кортеж (pod_name, namespace) или (None, None), если не найдено
        """
        if self._cached_controller:
            return self._cached_controller

        # Перебрать разные комбинации меток
        for label in self.INGRESS_CONTROLLER_LABELS:
            for ns in self.INGRESS_CONTROLLER_NAMESPACES:
                returncode, stdout, _ = self._run_kubectl(
                    ["get", "pods", "-l", label],
                    namespace=ns,
                    json_output=True
                )

                if returncode == 0:
                    try:
                        data = json.loads(stdout)
                        items = data.get("items", [])
                        if items:
                            pod_name = items[0].get("metadata", {}).get("name", "")
                            if pod_name:
                                self._cached_controller = (pod_name, ns)
                                return pod_name, ns
                    except json.JSONDecodeError:
                        continue

        # Перебрать все namespace с первой меткой
        for label in self.INGRESS_CONTROLLER_LABELS:
            returncode, stdout, _ = self._run_kubectl(
                ["get", "pods", "-l", label, "--all-namespaces"],
                json_output=True
            )

            if returncode == 0:
                try:
                    data = json.loads(stdout)
                    items = data.get("items", [])
                    if items:
                        pod_name = items[0].get("metadata", {}).get("name", "")
                        ns = items[0].get("metadata", {}).get("namespace", "")
                        if pod_name and ns:
                            self._cached_controller = (pod_name, ns)
                            return pod_name, ns
                except json.JSONDecodeError:
                    continue

        return None, None

    def get_nginx_config(self, pod_name: str, namespace: str) -> str:
        """
        Извлекает nginx.conf из пода ingress controller.

        Аргументы:
            pod_name: имя пода ingress controller
            namespace: namespace пода

        Возвращает:
            Содержимое nginx.conf в виде строки
        """
        # Частые расположения nginx.conf в ingress controller
        config_paths = [
            "/etc/nginx/nginx.conf",
            "/etc/nginx/nginx.conf.tmp",  # Некоторые контроллеры используют его
        ]

        for config_path in config_paths:
            try:
                result = subprocess.run(
                    ["kubectl", "exec", "-n", namespace, pod_name, "--",
                     "cat", config_path],
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    timeout=self.timeout
                )

                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout
            except subprocess.TimeoutExpired:
                raise KubectlError("Timeout getting nginx config from pod") from None
            except Exception:
                continue

        raise KubectlError("Could not read nginx.conf from ingress controller")

    def parse_nginx_config(self, config: str) -> dict:
        """
        Разбирает конфиг nginx с помощью crossplane.

        Аргументы:
            config: содержимое nginx.conf в виде строки

        Возвращает:
            Разобранный конфиг в виде dict

        Исключения:
            CrossplaneNotInstalledError: если crossplane недоступен
        """
        available, _ = self.check_crossplane()
        if not available:
            raise CrossplaneNotInstalledError(
                "crossplane not installed. Run: pip install crossplane"
            )

        # Записать конфиг во временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write(config)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["crossplane", "parse", temp_path, "--indent=2"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                raise IngressAnalyzerError(
                    f"crossplane parse failed: {result.stderr}"
                )

            return json.loads(result.stdout)

        except json.JSONDecodeError:
            raise IngressAnalyzerError("Failed to parse crossplane output") from None
        finally:
            os.unlink(temp_path)

    def extract_locations(self, parsed_config: dict) -> list[NginxLocation]:
        """
        Извлекает блоки location из разобранного конфига nginx.

        Аргументы:
            parsed_config: вывод parse_nginx_config()

        Возвращает:
            Список объектов NginxLocation
        """
        locations = []

        def find_locations(directives: list[dict]) -> None:
            """Рекурсивно ищет блоки location."""
            for directive in directives:
                if directive.get("directive") == "location":
                    loc = self._parse_location_directive(directive)
                    if loc:
                        locations.append(loc)

                # Рекурсия во вложенные блоки
                block = directive.get("block", [])
                if block:
                    find_locations(block)

        for config_file in parsed_config.get("config", []):
            find_locations(config_file.get("parsed", []))

        return locations

    def _parse_location_directive(self, directive: dict) -> NginxLocation | None:
        """Разбирает одну директиву location."""
        args = directive.get("args", [])
        block = directive.get("block", [])

        if not args:
            return None

        # Разобрать путь и модификатор
        modifier = None
        path = args[0]

        if len(args) > 1 and args[0] in ("=", "~", "~*", "^~"):
            modifier = args[0]
            path = args[1]

        # Извлечь proxy_pass и другие директивы
        proxy_pass = None
        upstream = None
        rewrite_rules = []
        raw_directives = []

        for sub_directive in block:
            dir_name = sub_directive.get("directive", "")
            dir_args = sub_directive.get("args", [])

            raw_directives.append(sub_directive)

            if dir_name == "proxy_pass":
                proxy_pass = " ".join(dir_args)
                # Извлечь имя upstream из proxy_pass
                if dir_args:
                    match = re.match(r'https?://([^/:]+)', dir_args[0])
                    if match:
                        upstream = match.group(1)

            elif dir_name in ("rewrite", "if"):
                rewrite_rules.append({
                    "directive": dir_name,
                    "args": dir_args
                })

        return NginxLocation(
            path=path,
            modifier=modifier,
            proxy_pass=proxy_pass,
            upstream=upstream,
            rewrite_rules=rewrite_rules,
            raw_directives=raw_directives
        )

    def extract_upstreams(self, parsed_config: dict) -> list[UpstreamInfo]:
        """
        Извлекает блоки upstream из разобранного конфига nginx.

        Аргументы:
            parsed_config: вывод parse_nginx_config()

        Возвращает:
            Список объектов UpstreamInfo
        """
        upstreams = []

        for config_file in parsed_config.get("config", []):
            for directive in config_file.get("parsed", []):
                if directive.get("directive") == "upstream":
                    upstream = self._parse_upstream_directive(directive)
                    if upstream:
                        upstreams.append(upstream)

        return upstreams

    def _parse_upstream_directive(self, directive: dict) -> UpstreamInfo | None:
        """Разбирает одну директиву upstream."""
        args = directive.get("args", [])
        block = directive.get("block", [])

        if not args:
            return None

        name = args[0]
        servers = []
        port = None
        raw_directives = []

        for sub_directive in block:
            dir_name = sub_directive.get("directive", "")
            dir_args = sub_directive.get("args", [])

            raw_directives.append(sub_directive)

            if dir_name == "server":
                server_addr = " ".join(dir_args)
                servers.append(server_addr)

                # Извлечь порт из адреса сервера
                if dir_args:
                    match = re.search(r':(\d+)', dir_args[0])
                    if match and port is None:
                        port = int(match.group(1))

        return UpstreamInfo(
            name=name,
            servers=servers,
            port=port,
            raw_directives=raw_directives
        )

    def check_service_endpoints(self, service: str, namespace: str | None = None) -> ServiceInfo:
        """
        Проверяет, есть ли у сервиса здоровые endpoint'ы.

        Аргументы:
            service: имя сервиса
            namespace: namespace (по умолчанию используется default)

        Возвращает:
            ServiceInfo с деталями по endpoint'ам
        """
        ns = namespace or self.default_namespace

        # Получить детали сервиса
        returncode, stdout, stderr = self._run_kubectl(
            ["get", "service", service],
            namespace=ns,
            json_output=True
        )

        if returncode != 0:
            raise KubectlError(f"Service '{service}' not found: {stderr}")

        try:
            svc_data = json.loads(stdout)
        except json.JSONDecodeError:
            raise KubectlError("Failed to parse service data") from None

        # Извлечь информацию о сервисе
        metadata = svc_data.get("metadata", {})
        spec = svc_data.get("spec", {})

        service_info = ServiceInfo(
            name=metadata.get("name", service),
            namespace=ns,
            type=spec.get("type", "ClusterIP"),
            ports=spec.get("ports", []),
            selector=spec.get("selector", {})
        )

        # Получить endpoint'ы
        returncode, stdout, _ = self._run_kubectl(
            ["get", "endpoints", service],
            namespace=ns,
            json_output=True
        )

        if returncode == 0:
            try:
                ep_data = json.loads(stdout)
                endpoints = self._parse_endpoints(ep_data)
                service_info.endpoints = endpoints
                service_info.total_endpoints = len(endpoints)
                service_info.healthy_endpoints = sum(1 for e in endpoints if e.ready)
            except json.JSONDecodeError:
                pass

        return service_info

    def _parse_endpoints(self, ep_data: dict) -> list[EndpointInfo]:
        """Разбирает endpoint'ы из вывода kubectl."""
        endpoints = []

        subsets = ep_data.get("subsets", [])
        for subset in subsets:
            addresses = subset.get("addresses", [])
            ports = subset.get("ports", [])

            for addr in addresses:
                for port_info in ports:
                    endpoints.append(EndpointInfo(
                        ip=addr.get("ip", ""),
                        port=port_info.get("port", 0),
                        ready=True,
                        pod_name=addr.get("targetRef", {}).get("name", "")
                    ))

            # Адреса NotReady
            not_ready = subset.get("notReadyAddresses", [])
            for addr in not_ready:
                for port_info in ports:
                    endpoints.append(EndpointInfo(
                        ip=addr.get("ip", ""),
                        port=port_info.get("port", 0),
                        ready=False,
                        pod_name=addr.get("targetRef", {}).get("name", "")
                    ))

        return endpoints

    def analyze_ingress(self, name: str, namespace: str | None = None) -> dict[str, Any]:
        """
        Полный анализ ingress.

        Аргументы:
            name: имя ingress
            namespace: namespace (по умолчанию используется default)

        Возвращает:
            Dict с полным анализом, включая:
            - ingress: IngressInfo
            - nginx_config: разобранный конфиг nginx (если доступен)
            - locations: список location nginx
            - upstreams: список upstream nginx
            - services: статус endpoint'ов сервисов
            - errors: список возникших ошибок
        """
        ns = namespace or self.default_namespace
        result = {
            "ingress": None,
            "nginx_config": None,
            "locations": [],
            "upstreams": [],
            "services": {},
            "errors": [],
            "warnings": [],
        }

        # Получить ingress
        ingress = self.get_ingress(name, ns)
        if not ingress:
            result["errors"].append(f"Ingress '{name}' not found in namespace '{ns}'")
            return result

        result["ingress"] = asdict(ingress)

        # Найти ingress controller
        pod_name, pod_ns = self.find_ingress_controller_pod()
        if not pod_name:
            result["warnings"].append(
                "Could not find nginx ingress controller pod. "
                "Nginx config analysis skipped."
            )
        else:
            # Получить и разобрать конфиг nginx
            try:
                nginx_config = self.get_nginx_config(
                    pod_name, pod_ns or self.default_namespace
                )
                result["nginx_config_raw"] = nginx_config[:5000] + "..." if len(nginx_config) > 5000 else nginx_config

                parsed = self.parse_nginx_config(nginx_config)
                result["locations"] = [asdict(loc) for loc in self.extract_locations(parsed)]
                result["upstreams"] = [asdict(up) for up in self.extract_upstreams(parsed)]

            except CrossplaneNotInstalledError:
                result["warnings"].append(
                    "crossplane not installed. Run: pip install crossplane"
                )
            except KubectlError as e:
                result["warnings"].append(f"Could not get nginx config: {e}")
            except IngressAnalyzerError as e:
                result["warnings"].append(f"Nginx config parsing failed: {e}")

        # Проверить endpoint'ы сервисов
        for service in ingress.services:
            svc_name = service.get("name")
            svc_ns = service.get("namespace", ns)

            if svc_name:
                try:
                    svc_info = self.check_service_endpoints(svc_name, svc_ns)
                    result["services"][svc_name] = asdict(svc_info)

                    # Предупреждение о сервисах без endpoint'ов
                    if svc_info.total_endpoints == 0:
                        result["warnings"].append(
                            f"Service '{svc_name}' has no endpoints"
                        )
                    elif svc_info.healthy_endpoints < svc_info.total_endpoints:
                        result["warnings"].append(
                            f"Service '{svc_name}': {svc_info.healthy_endpoints}/{svc_info.total_endpoints} endpoints healthy"
                        )
                except KubectlError as e:
                    result["warnings"].append(f"Could not check service '{svc_name}': {e}")

        return result


def format_analysis_summary(analysis: dict) -> str:
    """
    Форматирует результат анализа для показа.

    Аргументы:
        analysis: результат analyze_ingress()

    Возвращает:
        Отформатированную строку для показа
    """
    lines = []

    ingress = analysis.get("ingress")
    if ingress:
        lines.append(f"[bold]Ingress: {ingress['name']}[/bold] (namespace: {ingress['namespace']})")
        lines.append(f"Hosts: {', '.join(ingress['hosts']) or '*'}")

        if ingress.get('tls'):
            lines.append(f"TLS: Yes ({len(ingress['tls'])} certs)")
        else:
            lines.append("TLS: No")

        # Пути
        lines.append("\n[bold]Paths:[/bold]")
        for path in ingress.get('paths', []):
            svc_name = path.get('serviceName', '?')
            svc_port = path.get('servicePort', '?')
            host = path.get('host', '*')
            lines.append(f"  {path.get('path', '/')} → svc: {svc_name}:{svc_port} (host: {host})")

    # Статус сервисов
    services = analysis.get('services', {})
    if services:
        lines.append("\n[bold]Services:[/bold]")
        for svc_name, svc_info in services.items():
            healthy = svc_info.get('healthy_endpoints', 0)
            total = svc_info.get('total_endpoints', 0)
            status = "✓" if healthy == total and total > 0 else "⚠" if total > 0 else "✗"
            lines.append(f"  {status} {svc_name}: {healthy}/{total} endpoints")

    # Локации nginx
    locations = analysis.get('locations', [])
    if locations:
        lines.append(f"\n[bold]Nginx Locations: {len(locations)}[/bold]")

    # Предупреждения
    warnings = analysis.get('warnings', [])
    if warnings:
        lines.append("\n[yellow]Warnings:[/yellow]")
        for w in warnings:
            lines.append(f"  ⚠ {w}")

    # Ошибки
    errors = analysis.get('errors', [])
    if errors:
        lines.append("\n[red]Errors:[/red]")
        for e in errors:
            lines.append(f"  ✗ {e}")

    return "\n".join(lines)