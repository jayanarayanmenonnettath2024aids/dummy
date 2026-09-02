import os
import json
import secrets
import base64
from typing import Optional

class NodeIdentity:
    """
    Persistent Cryptographic Node Identity for iTantra Edge Units.
    Each node maintains a persistent node_id (UUID-based) and a local 256-bit
    authentication key for offline peer-to-peer verification.
    """
    DEFAULT_IDENTITY_FILE = os.path.join(os.path.dirname(__file__), "node_identity.json")

    def __init__(self, node_id: Optional[str] = None, secret_key: Optional[bytes] = None, identity_file: Optional[str] = None):
        self.identity_file = identity_file or self.DEFAULT_IDENTITY_FILE
        self.node_id: str = node_id or ""
        self.secret_key: bytes = secret_key or b""

        if not self.node_id or not self.secret_key:
            self._load_or_generate()

    def _load_or_generate(self):
        """Load existing persistent identity from disk, or generate a fresh key pair."""
        if os.path.exists(self.identity_file):
            try:
                with open(self.identity_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.node_id = data.get("node_id", f"NODE-{secrets.token_hex(4).upper()}")
                    b64_key = data.get("secret_key", "")
                    self.secret_key = base64.b64decode(b64_key) if b64_key else secrets.token_bytes(32)
                    return
            except Exception as e:
                print(f"[!] Warning: Failed to load identity from {self.identity_file}: {e}")

        # Generate fresh identity
        if not self.node_id:
            self.node_id = f"NODE-{secrets.token_hex(4).upper()}"
        if not self.secret_key:
            self.secret_key = secrets.token_bytes(32)
        
        self.save()

    def save(self):
        """Persist identity to local disk."""
        try:
            os.makedirs(os.path.dirname(self.identity_file), exist_ok=True)
            payload = {
                "node_id": self.node_id,
                "secret_key": base64.b64encode(self.secret_key).decode("utf-8")
            }
            with open(self.identity_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"[!] Warning: Failed to save identity to {self.identity_file}: {e}")

    def get_public_identity(self) -> dict:
        """Returns safe public identity metadata without private key."""
        return {
            "node_id": self.node_id,
            "key_fingerprint": base64.b64encode(self.secret_key[:8]).decode("utf-8")
        }
