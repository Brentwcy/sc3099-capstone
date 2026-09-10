"""
Redis Cache for Biometric SimHash Templates — Module 3.

Privacy controls implemented:
- AES-256-GCM authenticated encryption at rest (when TEMPLATE_ENCRYPTION_KEY is set)
- SimHash values are never written to logs
- delete_template() for revocation / consent withdrawal
- Versioned ciphertext format: "v1:<base64(nonce+ciphertext)>"
- Plaintext fallback when encryption key is absent (dev mode)
"""
from __future__ import annotations

import base64
import os
from typing import Dict, Optional

import numpy as np

from .logging_config import logger

# ---------------------------------------------------------------------------
# Optional AES-256-GCM encryption helpers
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False

_CIPHERTEXT_VERSION = "v1"
_NONCE_BYTES = 12  # 96-bit GCM nonce


def _build_aesgcm(key_b64: str) -> "_AESGCM | None":
    """Decode a base64url-encoded 32-byte key and return an AESGCM cipher."""
    if not _CRYPTO_AVAILABLE:
        return None
    try:
        raw_key = base64.urlsafe_b64decode(key_b64 + "==")  # tolerant padding
        if len(raw_key) != 32:
            logger.warning(
                "TEMPLATE_ENCRYPTION_KEY is not 32 bytes; encryption disabled",
                key_len=len(raw_key),
            )
            return None
        return _AESGCM(raw_key)
    except Exception as exc:
        logger.warning("Failed to load TEMPLATE_ENCRYPTION_KEY", error=str(exc))
        return None


def _encrypt(aesgcm: "_AESGCM", plaintext: str) -> str:
    """Return versioned ciphertext: 'v1:<base64(nonce||ct)>'."""
    nonce = os.urandom(_NONCE_BYTES)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    blob = base64.urlsafe_b64encode(nonce + ct).decode()
    return f"{_CIPHERTEXT_VERSION}:{blob}"


def _decrypt(aesgcm: "_AESGCM", stored: str) -> Optional[str]:
    """Decrypt a versioned ciphertext string; return None on any failure."""
    try:
        version, blob = stored.split(":", 1)
        if version != _CIPHERTEXT_VERSION:
            logger.warning("Unknown template ciphertext version", version=version)
            return None
        raw = base64.urlsafe_b64decode(blob + "==")
        nonce, ct = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception:
        # Intentionally no error detail — avoids leaking ciphertext in logs
        logger.warning("Template decryption failed; template may be corrupt or key rotated")
        return None


# ---------------------------------------------------------------------------
# EmbeddingCache
# ---------------------------------------------------------------------------

class EmbeddingCache:
    """Privacy-preserving cache for biometric SimHash templates."""

    def __init__(self, redis_url: Optional[str] = None, encryption_key: Optional[str] = None):
        self.redis_client = None
        self._memory_cache: Dict[str, str] = {}

        # Encryption cipher (None = dev/plaintext mode)
        self._aesgcm: Optional["_AESGCM"] = (
            _build_aesgcm(encryption_key) if encryption_key else None
        )

        if self._aesgcm:
            logger.info("Biometric template encryption: AES-256-GCM enabled")
        else:
            logger.warning(
                "Biometric template encryption disabled — "
                "set TEMPLATE_ENCRYPTION_KEY for production"
            )

        if redis_url:
            try:
                import redis as _redis  # local import to keep startup clean

                self.redis_client = _redis.Redis.from_url(redis_url, decode_responses=False)
                self.redis_client.ping()
                logger.info("Connected to Redis cache", url=redis_url)
            except Exception as exc:
                logger.warning("Redis not available, using in-memory cache", error=str(exc))
                self.redis_client = None

    # ------------------------------------------------------------------
    # Disabled raw-embedding API (privacy firewall)
    # ------------------------------------------------------------------

    def set_embedding(self, hash_key: str, embedding: np.ndarray, ttl_seconds: int = 86400) -> bool:  # noqa: ARG002
        """Raw embedding storage is permanently disabled for privacy."""
        return False

    def get_embedding(self, hash_key: str) -> Optional[np.ndarray]:  # noqa: ARG002
        """Raw embedding retrieval is permanently disabled for privacy."""
        return None

    # ------------------------------------------------------------------
    # Template API
    # ------------------------------------------------------------------

    def set_template(self, hash_key: str, simhash: str, ttl_seconds: Optional[int] = None) -> bool:
        """
        Persist an (optionally encrypted) SimHash template.

        - SimHash value is NEVER written to logs.
        - Encrypted with AES-256-GCM when a key is configured.
        - Stored permanently (no TTL) unless ttl_seconds is specified.
        """
        if not hash_key or not simhash:
            return False

        stored = _encrypt(self._aesgcm, simhash) if self._aesgcm else simhash

        # In-memory fallback always stores the encrypted/plain blob
        self._memory_cache[hash_key] = stored

        if self.redis_client:
            try:
                key = f"face_tpl:{hash_key}"
                if ttl_seconds:
                    self.redis_client.set(key, stored.encode(), ex=ttl_seconds)
                else:
                    self.redis_client.set(key, stored.encode())
            except Exception as exc:
                logger.debug("Redis template set failed, using memory fallback", error=str(exc))

        # Log only the truncated public hash — never the simhash/ciphertext
        logger.debug("Template stored", hash_prefix=hash_key[:8] + "...", encrypted=self._aesgcm is not None)
        return True

    def get_template(self, hash_key: str) -> Optional[str]:
        """
        Retrieve and decrypt a SimHash template.

        Returns the plaintext SimHash or None if missing/corrupt.
        SimHash value is never written to logs.
        """
        if not hash_key:
            return None

        stored: Optional[str] = None

        if self.redis_client:
            try:
                raw = self.redis_client.get(f"face_tpl:{hash_key}")
                if raw:
                    stored = raw.decode() if isinstance(raw, bytes) else str(raw)
            except Exception as exc:
                logger.debug("Redis template get failed", error=str(exc))

        if stored is None:
            stored = self._memory_cache.get(hash_key)

        if stored is None:
            return None

        if self._aesgcm:
            return _decrypt(self._aesgcm, stored)

        return stored

    def delete_template(self, hash_key: str) -> bool:
        """
        Permanently delete a biometric template on enrollment revocation.

        Called when:
        - A student withdraws biometric consent
        - An admin manually revokes face enrollment

        Returns True if the key was found and removed from at least one store.
        """
        if not hash_key:
            return False

        deleted = False

        if self.redis_client:
            try:
                n = self.redis_client.delete(f"face_tpl:{hash_key}")
                if n:
                    deleted = True
            except Exception as exc:
                logger.warning("Redis template delete failed", error=str(exc))

        if hash_key in self._memory_cache:
            del self._memory_cache[hash_key]
            deleted = True

        logger.info(
            "Biometric template deleted",
            hash_prefix=hash_key[:8] + "...",
            found=deleted,
        )
        return deleted
