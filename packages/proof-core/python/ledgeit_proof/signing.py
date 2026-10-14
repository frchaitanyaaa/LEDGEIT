"""Ed25519 signatures over hex digests (SPEC §6.1)."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class KeyPair:
    seed_b64: str
    public_key_b64: str

    def sign(self, hex_digest: str) -> str:
        return sign_hex_digest(hex_digest, self.seed_b64)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def keypair_from_seed(seed: bytes) -> KeyPair:
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    sk = SigningKey(seed)
    return KeyPair(seed_b64=_b64(seed), public_key_b64=_b64(bytes(sk.verify_key)))


def generate_keypair() -> KeyPair:
    sk = SigningKey.generate()
    return keypair_from_seed(bytes(sk))


def sign_hex_digest(hex_digest: str, seed_b64: str) -> str:
    if not _HEX64.match(hex_digest):
        raise ValueError("message must be a 64-char lowercase hex digest")
    sk = SigningKey(base64.b64decode(seed_b64))
    return _b64(sk.sign(hex_digest.encode("ascii")).signature)


def verify_hex_digest(hex_digest: str, signature_b64: str, public_key_b64: str) -> bool:
    try:
        vk = VerifyKey(base64.b64decode(public_key_b64, validate=True))
        vk.verify(hex_digest.encode("ascii"), base64.b64decode(signature_b64, validate=True))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False
