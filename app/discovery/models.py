import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class DiscoveredDevice:
    """
    Represents an auto-discovered iTantra node on the local network.
    """
    node_id: str
    device_name: str
    device_type: str = "desktop"
    host: str = "localhost"
    ip: str = "127.0.0.1"
    port: int = 65432
    languages: List[str] = field(default_factory=lambda: ["en"])
    capabilities: List[str] = field(default_factory=lambda: ["stt", "tts", "ptt"])
    protocol_version: str = "1.0"
    last_seen: float = field(default_factory=time.time)
    online: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert device model to serializable dictionary."""
        return {
            "node_id": self.node_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "host": self.host,
            "ip": self.ip,
            "port": self.port,
            "languages": self.languages,
            "capabilities": self.capabilities,
            "protocol_version": self.protocol_version,
            "last_seen": self.last_seen,
            "online": self.online
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscoveredDevice":
        """Construct a DiscoveredDevice from dictionary representation."""
        return cls(
            node_id=data.get("node_id", "UNKNOWN"),
            device_name=data.get("device_name", "Unknown Node"),
            device_type=data.get("device_type", "desktop"),
            host=data.get("host", "localhost"),
            ip=data.get("ip", "127.0.0.1"),
            port=int(data.get("port", 65432)),
            languages=data.get("languages", ["en"]),
            capabilities=data.get("capabilities", ["stt", "tts", "ptt"]),
            protocol_version=data.get("protocol_version", "1.0"),
            last_seen=float(data.get("last_seen", time.time())),
            online=bool(data.get("online", True))
        )
