"""
Redis Caching & In-Memory Fallback Client.
Caches normalized face embeddings by SHA-256 template hash.
"""
from typing import Optional, Dict
import numpy as np
from .logging_config import logger


class EmbeddingCache:
    """Cache manager for privacy-preserving face templates."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis_client = None
        self._memory_cache: Dict[str, bytes] = {}

        if redis_url:
            try:
                import redis
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=False)
                self.redis_client.ping()
                logger.info("Connected to Redis cache", url=redis_url)
            except Exception as e:
                logger.warning("Redis not available, using in-memory cache", error=str(e))
                self.redis_client = None

    def set_embedding(self, hash_key: str, embedding: np.ndarray, ttl_seconds: int = 86400) -> bool:
        """Reject raw embedding storage; use :meth:`set_template` instead."""
        return False

    def set_template(self, hash_key: str, simhash: str, ttl_seconds: int = 86400) -> bool:
        """Cache only the locality-sensitive template, never the raw embedding."""
        if not hash_key or not simhash:
            return False
        self._memory_cache[hash_key] = simhash
        if self.redis_client:
            try:
                self.redis_client.set(f"face_tpl:{hash_key}", simhash, ex=ttl_seconds)
            except Exception as e:
                logger.debug("Redis template set failed, falling back to memory", error=str(e))
        return True

    def get_template(self, hash_key: str) -> Optional[str]:
        """Retrieve a SimHash template by its public enrollment hash."""
        if not hash_key:
            return None
        if self.redis_client:
            try:
                raw = self.redis_client.get(f"face_tpl:{hash_key}")
                if raw:
                    return raw.decode() if isinstance(raw, bytes) else str(raw)
            except Exception as e:
                logger.debug("Redis template get failed", error=str(e))
        value = self._memory_cache.get(hash_key)
        return value if isinstance(value, str) else None

    def get_embedding(self, hash_key: str) -> Optional[np.ndarray]:
        """Raw embedding retrieval is disabled for privacy."""
        return None
