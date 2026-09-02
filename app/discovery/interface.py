from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from app.discovery.models import DiscoveredDevice

class DeviceDiscovery(ABC):
    """
    Abstract interface for local network device discovery.
    Allows swappable discovery providers (mDNS / Zeroconf, UDP beacon, BLE, etc.).
    """

    @abstractmethod
    def start(self) -> None:
        """Start the discovery service and begin advertising local node."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop advertising and listening for devices."""
        pass

    @abstractmethod
    def get_devices(self) -> List[DiscoveredDevice]:
        """Return list of all currently known discovered devices."""
        pass

    @abstractmethod
    def get_device(self, node_id: str) -> Optional[DiscoveredDevice]:
        """Get specific device by node_id if known."""
        pass

    @abstractmethod
    def on_device_added(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        """Register callback for when a new device is discovered."""
        pass

    @abstractmethod
    def on_device_removed(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        """Register callback for when a device goes offline or is removed."""
        pass

    @abstractmethod
    def on_device_updated(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        """Register callback for when a device's metadata or status changes."""
        pass
