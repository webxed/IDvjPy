"""
Kubernetes Ingress Analyzer Module

Provides tools for analyzing Kubernetes ingress configurations,
parsing nginx configs via crossplane, and debugging routing issues.
"""

import subprocess
import json
import tempfile
import os
import re
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict


@dataclass
class IngressInfo:
    """Represents a Kubernetes Ingress resource."""
    name: str
    namespace: str
    hosts: List[str]
    paths: List[Dict[str, str]]
    services: List[Dict[str, Any]]
    annotations: Dict[str, str] = field(default_factory=dict)
    tls: List[Dict[str, str]] = field(default_factory=list)
    raw_json: Dict = field(default_factory=dict, repr=False)


@dataclass
class NginxLocation:
    """Represents a parsed nginx location block."""
    path: str
    modifier: Optional[str] = None  # =, ~, ~*, ^~
    proxy_pass: Optional[str] = None
    upstream: Optional[str] = None
    rewrite_rules: List[Dict] = field(default_factory=list)
    raw_directives: List[Dict] = field(default_factory=list)


@dataclass
class UpstreamInfo:
    """Represents an nginx upstream block."""
    name: str
    servers: List[str] = field(default_factory=list)
    port: Optional[int] = None
    raw_directives: List[Dict] = field(default_factory=list)


@dataclass
class EndpointInfo:
    """Represents a Kubernetes endpoint."""
    ip: str
    port: int
    ready: bool = True
    pod_name: Optional[str] = None


@dataclass
class ServiceInfo:
    """Represents a Kubernetes service with endpoints."""
    name: str
    namespace: str
    type: str
    ports: List[Dict]
    selector: Dict[str, str]
    endpoints: List[EndpointInfo] = field(default_factory=list)
    healthy_endpoints: int = 0
    total_endpoints: int = 0


class IngressAnalyzerError(Exception):
    """Base exception for IngressAnalyzer."""
    pass


class CrossplaneNotInstalledError(IngressAnalyzerError):
    """Raised when crossplane is not installed."""
    pass


class KubectlError(IngressAnalyzerError):
    """Raised when kubectl command fails."""
    pass


class IngressAnalyzer:
    """
    Main class for Kubernetes ingress analysis.

    Usage:
        analyzer = IngressAnalyzer()
        ingresses = analyzer.list_ingresses()
        result = analyzer.analyze_ingress("my-ingress", "default")
    """

    # Common labels for nginx ingress controller
    INGRESS_CONTROLLER_LABELS = [
        "app.kubernetes.io/component=controller",
        "app=nginx-ingress",
        "app=ingress-nginx",
        "name=ingress-nginx",
        "app.kubernetes.io/name=ingress-nginx",
    ]

    # Common namespaces for ingress controller
    INGRESS_CONTROLLER_NAMESPACES = [
        "ingress-nginx",
        "kube-system",
        "nginx-ingress",
    ]

    def __init__(self, timeout: int = 30, default_namespace: str = "default"):
        self.timeout = timeout
        self.default_namespace = default_namespace
        self._crossplane_available: Optional[bool] = None
        self._cached_controller: Optional[Tuple[str, str]] = None

    def _run_kubectl(self, args: List[str], namespace: Optional[str] = None,
                     json_output: bool = True) -> Tuple[int, str, str]:
        """
        Run kubectl command and return (returncode, stdout, stderr).

        Args:
            args: kubectl arguments (without 'kubectl')
            namespace: namespace to use (optional, adds -n flag)
            json_output: add -o json flag

        Returns:
            Tuple of (returncode, stdout, stderr)
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
                timeout=self.timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            raise KubectlError(f"kubectl command timed out after {self.timeout}s")
        except FileNotFoundError:
            raise KubectlError("kubectl not found. Please install kubectl.")

    def check_crossplane(self) -> Tuple[bool, str]:
        """
        Check if crossplane is installed and available.

        Returns:
            Tuple of (is_available, version_or_error)
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

    def install_crossplane(self) -> Tuple[bool, str]:
        """
        Install crossplane via pip.

        Returns:
            Tuple of (success, message)
        """
        try:
            result = subprocess.run(
                ["pip", "install", "crossplane"],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                self._crossplane_available = True
                return True, "crossplane installed successfully"
            return False, f"pip install failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, f"Installation error: {e}"

    def list_ingresses(self, namespace: Optional[str] = None) -> List[IngressInfo]:
        """
        Get ingresses.

        Args:
            namespace: Specific namespace or None for all namespaces

        Returns:
            List of IngressInfo objects

        Raises:
            KubectlError: If kubectl command fails
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
            raise KubectlError("Failed to parse kubectl output")

        ingresses = []
        for item in data.get("items", []):
            ingress = self._parse_ingress_item(item)
            if ingress:
                ingresses.append(ingress)

        return ingresses

    def _parse_ingress_item(self, item: Dict) -> Optional[IngressInfo]:
        """Parse a single ingress item from kubectl output."""
        try:
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})

            name = metadata.get("name", "")
            namespace = metadata.get("namespace", self.default_namespace)
            annotations = metadata.get("annotations", {})

            # Extract hosts
            hosts = []
            tls = spec.get("tls", [])
            for tls_entry in tls:
                for host in tls_entry.get("hosts", []):
                    if host not in hosts:
                        hosts.append(host)

            # Extract paths and services from rules
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

                        # Track unique services
                        svc_name = service.get("name", "")
                        if svc_name and not any(s.get("name") == svc_name for s in services):
                            services.append({
                                "name": svc_name,
                                "port": path_info["servicePort"],
                                "namespace": namespace,
                            })

                    paths.append(path_info)

            # Handle default backend
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

    def get_ingress(self, name: str, namespace: Optional[str] = None) -> Optional[IngressInfo]:
        """
        Get specific ingress details.

        Args:
            name: Ingress name
            namespace: Namespace (uses default if not specified)

        Returns:
            IngressInfo or None if not found
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

    def find_ingress_controller_pod(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Find nginx ingress controller pod name and namespace.

        Returns:
            Tuple of (pod_name, namespace) or (None, None) if not found
        """
        if self._cached_controller:
            return self._cached_controller

        # Try different label combinations
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

        # Try all namespaces with first label
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
        Extract nginx.conf from ingress controller pod.

        Args:
            pod_name: Name of the ingress controller pod
            namespace: Namespace of the pod

        Returns:
            nginx.conf content as string
        """
        # Common nginx.conf locations in ingress controllers
        config_paths = [
            "/etc/nginx/nginx.conf",
            "/etc/nginx/nginx.conf.tmp",  # Some controllers use this
        ]

        for config_path in config_paths:
            try:
                result = subprocess.run(
                    ["kubectl", "exec", "-n", namespace, pod_name, "--",
                     "cat", config_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )

                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout
            except subprocess.TimeoutExpired:
                raise KubectlError("Timeout getting nginx config from pod")
            except Exception:
                continue

        raise KubectlError("Could not read nginx.conf from ingress controller")

    def parse_nginx_config(self, config: str) -> Dict:
        """
        Parse nginx config using crossplane.

        Args:
            config: nginx.conf content as string

        Returns:
            Parsed config as dict

        Raises:
            CrossplaneNotInstalledError: If crossplane is not available
        """
        available, _ = self.check_crossplane()
        if not available:
            raise CrossplaneNotInstalledError(
                "crossplane not installed. Run: pip install crossplane"
            )

        # Write config to temp file
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
            raise IngressAnalyzerError("Failed to parse crossplane output")
        finally:
            os.unlink(temp_path)

    def extract_locations(self, parsed_config: Dict) -> List[NginxLocation]:
        """
        Extract location blocks from parsed nginx config.

        Args:
            parsed_config: Output from parse_nginx_config()

        Returns:
            List of NginxLocation objects
        """
        locations = []

        def find_locations(directives: List[Dict]) -> None:
            """Recursively find location blocks."""
            for directive in directives:
                if directive.get("directive") == "location":
                    loc = self._parse_location_directive(directive)
                    if loc:
                        locations.append(loc)

                # Recurse into nested blocks
                block = directive.get("block", [])
                if block:
                    find_locations(block)

        for config_file in parsed_config.get("config", []):
            find_locations(config_file.get("parsed", []))

        return locations

    def _parse_location_directive(self, directive: Dict) -> Optional[NginxLocation]:
        """Parse a single location directive."""
        args = directive.get("args", [])
        block = directive.get("block", [])

        if not args:
            return None

        # Parse path and modifier
        modifier = None
        path = args[0]

        if len(args) > 1 and args[0] in ("=", "~", "~*", "^~"):
            modifier = args[0]
            path = args[1]

        # Extract proxy_pass and other directives
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
                # Extract upstream name from proxy_pass
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

    def extract_upstreams(self, parsed_config: Dict) -> List[UpstreamInfo]:
        """
        Extract upstream blocks from parsed nginx config.

        Args:
            parsed_config: Output from parse_nginx_config()

        Returns:
            List of UpstreamInfo objects
        """
        upstreams = []

        for config_file in parsed_config.get("config", []):
            for directive in config_file.get("parsed", []):
                if directive.get("directive") == "upstream":
                    upstream = self._parse_upstream_directive(directive)
                    if upstream:
                        upstreams.append(upstream)

        return upstreams

    def _parse_upstream_directive(self, directive: Dict) -> Optional[UpstreamInfo]:
        """Parse a single upstream directive."""
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

                # Extract port from server address
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

    def check_service_endpoints(self, service: str, namespace: Optional[str] = None) -> ServiceInfo:
        """
        Check if service has healthy endpoints.

        Args:
            service: Service name
            namespace: Namespace (uses default if not specified)

        Returns:
            ServiceInfo with endpoint details
        """
        ns = namespace or self.default_namespace

        # Get service details
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
            raise KubectlError("Failed to parse service data")

        # Extract service info
        metadata = svc_data.get("metadata", {})
        spec = svc_data.get("spec", {})

        service_info = ServiceInfo(
            name=metadata.get("name", service),
            namespace=ns,
            type=spec.get("type", "ClusterIP"),
            ports=spec.get("ports", []),
            selector=spec.get("selector", {})
        )

        # Get endpoints
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

    def _parse_endpoints(self, ep_data: Dict) -> List[EndpointInfo]:
        """Parse endpoints from kubectl output."""
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

            # NotReady addresses
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

    def analyze_ingress(self, name: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Full analysis of an ingress.

        Args:
            name: Ingress name
            namespace: Namespace (uses default if not specified)

        Returns:
            Dict with complete analysis including:
            - ingress: IngressInfo
            - nginx_config: parsed nginx config (if available)
            - locations: list of nginx locations
            - upstreams: list of nginx upstreams
            - services: service endpoint status
            - errors: list of any errors encountered
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

        # Get ingress
        ingress = self.get_ingress(name, ns)
        if not ingress:
            result["errors"].append(f"Ingress '{name}' not found in namespace '{ns}'")
            return result

        result["ingress"] = asdict(ingress)

        # Find ingress controller
        pod_name, pod_ns = self.find_ingress_controller_pod()
        if not pod_name:
            result["warnings"].append(
                "Could not find nginx ingress controller pod. "
                "Nginx config analysis skipped."
            )
        else:
            # Get and parse nginx config
            try:
                nginx_config = self.get_nginx_config(pod_name, pod_ns)
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

        # Check service endpoints
        for service in ingress.services:
            svc_name = service.get("name")
            svc_ns = service.get("namespace", ns)

            if svc_name:
                try:
                    svc_info = self.check_service_endpoints(svc_name, svc_ns)
                    result["services"][svc_name] = asdict(svc_info)

                    # Add warning for services with no endpoints
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


def format_analysis_summary(analysis: Dict) -> str:
    """
    Format analysis result for display.

    Args:
        analysis: Result from analyze_ingress()

    Returns:
        Formatted string for display
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

        # Paths
        lines.append("\n[bold]Paths:[/bold]")
        for path in ingress.get('paths', []):
            svc_name = path.get('serviceName', '?')
            svc_port = path.get('servicePort', '?')
            host = path.get('host', '*')
            lines.append(f"  {path.get('path', '/')} → svc: {svc_name}:{svc_port} (host: {host})")

    # Services status
    services = analysis.get('services', {})
    if services:
        lines.append("\n[bold]Services:[/bold]")
        for svc_name, svc_info in services.items():
            healthy = svc_info.get('healthy_endpoints', 0)
            total = svc_info.get('total_endpoints', 0)
            status = "✓" if healthy == total and total > 0 else "⚠" if total > 0 else "✗"
            lines.append(f"  {status} {svc_name}: {healthy}/{total} endpoints")

    # Nginx locations
    locations = analysis.get('locations', [])
    if locations:
        lines.append(f"\n[bold]Nginx Locations: {len(locations)}[/bold]")

    # Warnings
    warnings = analysis.get('warnings', [])
    if warnings:
        lines.append("\n[yellow]Warnings:[/yellow]")
        for w in warnings:
            lines.append(f"  ⚠ {w}")

    # Errors
    errors = analysis.get('errors', [])
    if errors:
        lines.append("\n[red]Errors:[/red]")
        for e in errors:
            lines.append(f"  ✗ {e}")

    return "\n".join(lines)