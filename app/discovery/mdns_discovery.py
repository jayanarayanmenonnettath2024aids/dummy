import time
import socket
import threading
from typing import List, Dict, Optional, Callable, Any
from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, ServiceListener, IPVersion

from app.discovery.models import DiscoveredDevice
from app.discovery.interface import DeviceDiscovery

SERVICE_TYPE = "_itantra._tcp.local."

class _MdnsListener(ServiceListener):
    """Internal Zeroconf listener that dispatches events to MdnsDeviceDiscovery."""
    def __init__(self, discovery: "MdnsDeviceDiscovery"):
        self.discovery = discovery

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.discovery._handle_service_resolved(zc, type_, name)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.discovery._handle_service_resolved(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.discovery._handle_service_removed(name)


class MdnsDeviceDiscovery(DeviceDiscovery):
    """
    mDNS / DNS-SD implementation for automatic zero-configuration iTantra node discovery.
    Uses Zeroconf to advertise local node properties and discover nearby peer nodes on the LAN.
    """
    def __init__(
        self,
        node_id: Optional[str] = None,
        device_name: Optional[str] = None,
        tcp_port: int = 65432,
        local_ip: Optional[str] = None,
        device_type: str = "desktop",
        languages: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        protocol_version: str = "1.0",
        stale_timeout: float = 120.0,
        zeroconf_instance: Optional[Zeroconf] = None
    ):
        self.node_id = node_id or socket.gethostname() or "NODE-ALPHA"
        self.device_name = device_name or self.node_id
        self.tcp_port = tcp_port
        self.local_ip = local_ip or self._detect_local_ip()
        self.device_type = device_type
        self.languages = languages or ["en"]
        self.capabilities = capabilities or ["stt", "tts", "ptt"]
        self.protocol_version = protocol_version
        self.stale_timeout = stale_timeout

        self._zc = zeroconf_instance
        self._owns_zc = zeroconf_instance is None
        self._service_info: Optional[ServiceInfo] = None
        self._browser: Optional[ServiceBrowser] = None
        self._listener: Optional[_MdnsListener] = None

        self._devices: Dict[str, DiscoveredDevice] = {}
        self._service_to_node: Dict[str, str] = {}
        self._lock = threading.Lock()

        self._added_callbacks: List[Callable[[DiscoveredDevice], None]] = []
        self._removed_callbacks: List[Callable[[DiscoveredDevice], None]] = []
        self._updated_callbacks: List[Callable[[DiscoveredDevice], None]] = []

        self._is_running = False
        self._stale_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None

    def _detect_local_ip(self) -> str:
        """Helper to get local IPv4 address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _create_service_info(self) -> ServiceInfo:
        """Create Zeroconf ServiceInfo for local node advertisement."""
        node_str = str(self.node_id or socket.gethostname() or "NODE-ALPHA")
        self.node_id = node_str
        sanitized_node_id = node_str.replace(" ", "-")
        service_name = f"{sanitized_node_id}.{SERVICE_TYPE}"
        server_host = f"{sanitized_node_id}.local."

        try:
            ip_bytes = socket.inet_aton(self.local_ip)
        except Exception:
            ip_bytes = socket.inet_aton("127.0.0.1")

        properties = {
            b"node_id": self.node_id.encode("utf-8"),
            b"device_name": self.device_name.encode("utf-8"),
            b"device_type": self.device_type.encode("utf-8"),
            b"languages": ",".join(self.languages).encode("utf-8"),
            b"capabilities": ",".join(self.capabilities).encode("utf-8"),
            b"version": self.protocol_version.encode("utf-8")
        }

        return ServiceInfo(
            type_=SERVICE_TYPE,
            name=service_name,
            addresses=[ip_bytes],
            port=self.tcp_port,
            properties=properties,
            server=server_host
        )

    def start(self) -> None:
        """Start advertising local node and browsing for network peers."""
        if self._is_running:
            return

        self._is_running = True
        if self._zc is None:
            self._zc = Zeroconf(ip_version=IPVersion.V4Only)

        # 1. Register local service
        self._service_info = self._create_service_info()
        try:
            self._zc.register_service(self._service_info)
            print(f"[mDNS] Registered service: {self._service_info.name} on {self.local_ip}:{self.tcp_port}")
        except Exception as e:
            print(f"[!] mDNS Service Registration Error: {e}")

        # 2. Browse for remote services
        self._listener = _MdnsListener(self)
        self._browser = ServiceBrowser(self._zc, SERVICE_TYPE, self._listener)

        # 3. Start background stale timeout checker and announcement heartbeat
        self._stale_thread = threading.Thread(target=self._stale_check_loop, daemon=True)
        self._stale_thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_announcement_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_announcement_loop(self) -> None:
        """Periodically re-announce local node on LAN so peer nodes maintain active status."""
        while self._is_running:
            time.sleep(15.0)
            if not self._is_running:
                break
            if self._zc and self._service_info:
                try:
                    self._zc.update_service(self._service_info)
                except Exception:
                    pass

    def _handle_service_resolved(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Process resolved mDNS service information."""
        info = zc.get_service_info(type_, name)
        if not info:
            return

        # Parse properties safely
        props: Dict[str, str] = {}
        if info.properties:
            for k, v in info.properties.items():
                key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                props[key] = val

        remote_node_id = props.get("node_id")
        if not remote_node_id:
            # Fallback to service name prefix
            remote_node_id = name.split(".")[0]

        # Filter out self-announcement
        if remote_node_id == self.node_id:
            return

        # Extract IP address
        ip_addr = "127.0.0.1"
        try:
            if info.addresses and len(info.addresses) > 0 and isinstance(info.addresses[0], (bytes, bytearray)):
                ip_addr = socket.inet_ntoa(info.addresses[0])
            elif hasattr(info, "parsed_scoped_addresses") and callable(info.parsed_scoped_addresses):
                addrs = info.parsed_scoped_addresses()
                if addrs and isinstance(addrs, list) and len(addrs) > 0 and isinstance(addrs[0], str):
                    ip_addr = addrs[0]
        except Exception:
            ip_addr = "127.0.0.1"

        device_name = props.get("device_name", remote_node_id)
        device_type = props.get("device_type", "desktop")
        languages = props.get("languages", "en").split(",") if props.get("languages") else ["en"]
        capabilities = props.get("capabilities", "stt,tts,ptt").split(",") if props.get("capabilities") else ["stt", "tts", "ptt"]
        protocol_version = props.get("version", "1.0")

        now = time.time()
        was_added = False
        was_updated = False
        target_device = None

        with self._lock:
            self._service_to_node[name] = remote_node_id
            if remote_node_id not in self._devices:
                target_device = DiscoveredDevice(
                    node_id=remote_node_id,
                    device_name=device_name,
                    device_type=device_type,
                    host=info.server or f"{remote_node_id}.local.",
                    ip=ip_addr,
                    port=info.port,
                    languages=languages,
                    capabilities=capabilities,
                    protocol_version=protocol_version,
                    last_seen=now,
                    online=True
                )
                self._devices[remote_node_id] = target_device
                was_added = True
            else:
                target_device = self._devices[remote_node_id]
                target_device.device_name = device_name
                target_device.device_type = device_type
                target_device.ip = ip_addr
                target_device.port = info.port
                target_device.languages = languages
                target_device.capabilities = capabilities
                target_device.protocol_version = protocol_version
                target_device.last_seen = now
                if not target_device.online:
                    target_device.online = True
                    was_updated = True
                else:
                    was_updated = True

        if was_added and target_device:
            print(f"[mDNS] Discovered new peer node: {target_device.device_name} ({target_device.node_id}) at {target_device.ip}:{target_device.port}")
            self._notify_added(target_device)
        elif was_updated and target_device:
            self._notify_updated(target_device)

    def _handle_service_removed(self, name: str) -> None:
        """Handle service removal event when remote node stops."""
        target_device = None
        with self._lock:
            node_id = self._service_to_node.get(name)
            if node_id and node_id in self._devices:
                target_device = self._devices[node_id]
                target_device.online = False

        if target_device:
            print(f"[mDNS] Peer node went offline: {target_device.device_name} ({target_device.node_id})")
            self._notify_removed(target_device)
            self._notify_updated(target_device)

    def _stale_check_loop(self) -> None:
        """Periodically check for devices that have not sent keepalives within stale_timeout."""
        while self._is_running:
            time.sleep(2.0)
            now = time.time()
            stale_devices = []

            with self._lock:
                for device in self._devices.values():
                    if device.online and (now - device.last_seen > self.stale_timeout):
                        device.online = False
                        stale_devices.append(device)

            for dev in stale_devices:
                print(f"[mDNS] Stale timeout reached for peer: {dev.device_name} ({dev.node_id}) -> Marked OFFLINE")
                self._notify_removed(dev)
                self._notify_updated(dev)

    def get_devices(self) -> List[DiscoveredDevice]:
        """Return shallow copy list of all known devices."""
        with self._lock:
            return list(self._devices.values())

    def get_device(self, node_id: str) -> Optional[DiscoveredDevice]:
        """Retrieve a specific device by its node_id."""
        with self._lock:
            return self._devices.get(node_id)

    def on_device_added(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        self._added_callbacks.append(callback)

    def on_device_removed(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        self._removed_callbacks.append(callback)

    def on_device_updated(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        self._updated_callbacks.append(callback)

    def _notify_added(self, device: DiscoveredDevice) -> None:
        for cb in list(self._added_callbacks):
            try:
                cb(device)
            except Exception as e:
                print(f"[!] Error in device_added callback: {e}")

    def _notify_removed(self, device: DiscoveredDevice) -> None:
        for cb in list(self._removed_callbacks):
            try:
                cb(device)
            except Exception as e:
                print(f"[!] Error in device_removed callback: {e}")

    def _notify_updated(self, device: DiscoveredDevice) -> None:
        for cb in list(self._updated_callbacks):
            try:
                cb(device)
            except Exception as e:
                print(f"[!] Error in device_updated callback: {e}")

    def stop(self) -> None:
        """Cleanly unregister local service and stop browser."""
        self._is_running = False
        if self._browser and self._zc:
            try:
                self._browser.cancel()
            except Exception:
                pass
            self._browser = None

        if self._service_info and self._zc:
            try:
                self._zc.unregister_service(self._service_info)
                print(f"[mDNS] Unregistered service: {self._service_info.name}")
            except Exception:
                pass
            self._service_info = None

        if self._owns_zc and self._zc:
            try:
                self._zc.close()
            except Exception:
                pass
            self._zc = None
