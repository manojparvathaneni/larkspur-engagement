"""Loads the sealed scenario that sets Larkspur's hidden facts and incidents.

The scenario ships encrypted as scenario.enc so the facts can't be read by accident.
The world needs LARKSPUR_SCENARIO_KEY to decrypt it. For local work without the key,
set LARKSPUR_SCENARIO_FILE to a plaintext JSON file instead.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).parent


def load() -> dict:
    plain = os.environ.get("LARKSPUR_SCENARIO_FILE")
    if plain:
        return json.loads(Path(plain).read_text())
    key = os.environ.get("LARKSPUR_SCENARIO_KEY")
    if not key:
        raise SystemExit("LARKSPUR_SCENARIO_KEY is not set; the scenario can't be decrypted")
    from cryptography.fernet import Fernet
    return json.loads(Fernet(key.encode()).decrypt((HERE / "scenario.enc").read_bytes()))


def seal(plain_path: str, key: str | None = None) -> str:
    """Encrypt a plaintext scenario into scenario.enc. Returns the key."""
    from cryptography.fernet import Fernet
    key = key or Fernet.generate_key().decode()
    (HERE / "scenario.enc").write_bytes(Fernet(key.encode()).encrypt(Path(plain_path).read_bytes()))
    return key
