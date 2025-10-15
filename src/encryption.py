"""Utility functions for end-to-end encryption using X25519 and AES-GCM."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


HKDF_SALT = b"temp-chat-e2ee"
HKDF_INFO = b"shared-room-key"
AES_KEY_SIZE = 32
NONCE_SIZE = 12


@dataclass
class KeyPair:
    """Represents an X25519 key pair with convenience helpers."""

    private_key: x25519.X25519PrivateKey
    public_key: x25519.X25519PublicKey

    @classmethod
    def generate(cls) -> "KeyPair":
        private_key = x25519.X25519PrivateKey.generate()
        return cls(private_key=private_key, public_key=private_key.public_key())

    def serialize_public_key(self) -> str:
        return base64.b64encode(
            self.public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

    @staticmethod
    def deserialize_public_key(data: str) -> x25519.X25519PublicKey:
        return x25519.X25519PublicKey.from_public_bytes(base64.b64decode(data))


def derive_shared_key(
    private_key: x25519.X25519PrivateKey,
    peer_public_key: x25519.X25519PublicKey,
) -> bytes:
    """Derive a 256-bit AES key using HKDF."""

    shared_secret = private_key.exchange(peer_public_key)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=HKDF_SALT,
        info=HKDF_INFO,
    )
    return hkdf.derive(shared_secret)


def encrypt_message(key: bytes, plaintext: str) -> Tuple[str, str]:
    """Encrypt a plaintext string and return base64 nonce and ciphertext."""

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(ciphertext).decode("ascii"),
    )


def decrypt_message(key: bytes, nonce_b64: str, ciphertext_b64: str) -> str:
    """Decrypt ciphertext using AES-GCM returning the original message."""

    aesgcm = AESGCM(key)
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
