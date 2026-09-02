import os
import json
import base64
from typing import Dict, Any, Optional, List

class TrustStore:
    """
    Local Offline Trust Store for iTantra nodes.
    Maintains peer trust statuses (TRUSTED, UNPAIRED, REVOKED) and pairwise shared keys
    without central servers or internet connectivity.
    """
    DEFAULT_TRUST_FILE = os.path.join(os.path.dirname(__file__), "trust_store.json")

    STATUS_TRUSTED = "TRUSTED"
    STATUS_UNPAIRED = "UNPAIRED"
    STATUS_REVOKED = "REVOKED"

    def __init__(self, trust_file: Optional[str] = None):
        self.trust_file = trust_file or self.DEFAULT_TRUST_FILE
        self._store: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """Load trust store from disk."""
        if self.trust_file == ":memory:":
            self._store = {}
            return
        if os.path.exists(self.trust_file):
            try:
                with open(self.trust_file, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
            except Exception as e:
                print(f"[!] Warning: Failed to load trust store from {self.trust_file}: {e}")
                self._store = {}

    def save(self):
        """Save trust store to disk."""
        if self.trust_file == ":memory:":
            return
        try:
            os.makedirs(os.path.dirname(self.trust_file), exist_ok=True)
            with open(self.trust_file, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2)
        except Exception as e:
            print(f"[!] Warning: Failed to save trust store to {self.trust_file}: {e}")

    def pair_device(self, node_id: str, secret_key: bytes, name: str = "", status: str = STATUS_TRUSTED):
        """Pair a device and assign its trusted cryptographic key."""
        self._store[node_id] = {
            "node_id": node_id,
            "name": name or node_id,
            "status": status,
            "secret_key": base64.b64encode(secret_key).decode("utf-8")
        }
        self.save()

    def set_trust_status(self, node_id: str, status: str):
        """Update trust status for a device."""
        if node_id in self._store:
            self._store[node_id]["status"] = status
            self.save()
        else:
            self._store[node_id] = {
                "node_id": node_id,
                "name": node_id,
                "status": status,
                "secret_key": ""
            }
            self.save()

    def is_trusted(self, node_id: str) -> bool:
        """Check if node is paired and trusted."""
        entry = self._store.get(node_id)
        if not entry:
            return False
        return entry.get("status") == self.STATUS_TRUSTED and bool(entry.get("secret_key"))

    def get_peer_key(self, node_id: str) -> Optional[bytes]:
        """Retrieve the pairwise secret key for a trusted node."""
        entry = self._store.get(node_id)
        if not entry or entry.get("status") != self.STATUS_TRUSTED:
            return None
        b64_key = entry.get("secret_key", "")
        return base64.b64decode(b64_key) if b64_key else None

    def get_device_status(self, node_id: str) -> str:
        """Returns trust status (TRUSTED, UNPAIRED, REVOKED)."""
        entry = self._store.get(node_id)
        return entry.get("status", self.STATUS_UNPAIRED) if entry else self.STATUS_UNPAIRED

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all devices in trust store."""
        return list(self._store.values())
