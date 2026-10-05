"""Password hashing, key derivation and envelope encryption for local accounts (DESIGN_V2, DEVIATIONS D22).

Each user has a random 256-bit data key (DEK). It is stored twice, wrapped with AES-256-GCM under a key derived
(argon2id) from the password and under one derived from the recovery code. Every content field is AES-256-GCM under
the DEK with associated data "table:column:row_id", so a ciphertext copied to another row or column fails to decrypt.
"""

import base64
import os
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.app.config import Settings

KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12
RECOVERY_CHARS = 20
RECOVERY_GROUP = 4
_WRAP_AAD = b"haki:dek"


class CryptoError(Exception):
    """A ciphertext failed authentication: wrong key, tampered bytes or a swapped AAD."""


@dataclass(frozen=True)
class KdfParams:
    """argon2id cost parameters (the same for password hashes and key derivation)."""

    time_cost: int
    memory_kib: int
    parallelism: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "KdfParams":
        """Parameters from config.py."""
        return cls(settings.argon2_time_cost, settings.argon2_memory_kib, settings.argon2_parallelism)

    def hasher(self) -> PasswordHasher:
        """An argon2id PasswordHasher with these parameters."""
        return PasswordHasher(time_cost=self.time_cost, memory_cost=self.memory_kib, parallelism=self.parallelism)


def hash_password(password: str, params: KdfParams) -> str:
    """Encoded argon2id hash (salt and parameters included)."""
    return params.hasher().hash(password)


def verify_password(encoded: str, password: str, params: KdfParams) -> bool:
    """True if password matches the encoded hash."""
    try:
        return params.hasher().verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def derive_key(secret: str, salt: bytes, params: KdfParams) -> bytes:
    """A 256-bit key-encryption key from a password or recovery code (argon2id raw)."""
    return hash_secret_raw(
        secret.encode("utf-8"),
        salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_kib,
        parallelism=params.parallelism,
        hash_len=KEY_BYTES,
        type=Type.ID,
    )


def new_key() -> bytes:
    """A random 256-bit key (the DEK)."""
    return os.urandom(KEY_BYTES)


def new_salt() -> bytes:
    """A random KDF salt."""
    return os.urandom(SALT_BYTES)


def _seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def _open(key: bytes, sealed: bytes, aad: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(sealed[:NONCE_BYTES], sealed[NONCE_BYTES:], aad)
    except (InvalidTag, ValueError) as exc:
        raise CryptoError("ciphertext failed authentication") from exc


def wrap_key(kek: bytes, dek: bytes) -> bytes:
    """The DEK encrypted under a key-encryption key."""
    return _seal(kek, dek, _WRAP_AAD)


def unwrap_key(kek: bytes, wrapped: bytes) -> bytes:
    """The DEK, or CryptoError if kek is wrong or wrapped was altered."""
    return _open(kek, wrapped, _WRAP_AAD)


def field_aad(table: str, column: str, row_id: str) -> bytes:
    """Associated data binding a ciphertext to its table, column and row."""
    return f"{table}:{column}:{row_id}".encode()


def encrypt_field(dek: bytes, plaintext: str, aad: bytes) -> bytes:
    """nonce ‖ AES-256-GCM(dek, plaintext) for one stored field."""
    return _seal(dek, plaintext.encode("utf-8"), aad)


def decrypt_field(dek: bytes, sealed: bytes, aad: bytes) -> str:
    """The plaintext of a stored field, or CryptoError."""
    return _open(dek, sealed, aad).decode("utf-8")


def new_recovery_code() -> str:
    """20 random base32 characters (100 bits), shown in groups of 4: ABCD-EFGH-…"""
    raw = base64.b32encode(secrets.token_bytes(RECOVERY_CHARS * 5 // 8)).decode("ascii")[:RECOVERY_CHARS]
    return "-".join(raw[i : i + RECOVERY_GROUP] for i in range(0, RECOVERY_CHARS, RECOVERY_GROUP))


def normalise_recovery_code(code: str) -> str:
    """The code as typed (any case, spaces or dashes) in its canonical grouped form."""
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    return "-".join(raw[i : i + RECOVERY_GROUP] for i in range(0, len(raw), RECOVERY_GROUP))
