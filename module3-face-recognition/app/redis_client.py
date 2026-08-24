"""
Redis Caching & In-Memory Fallback Client.
Caches normalized face embeddings by SHA-256 template hash.
"""
from typing import Optional, Dict
import numpy as np
from .logging_config import logger


class EmbeddingCache:
    """Cache manager for facial embeddings with Redis and in-memory fallback."""

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
        """Cache embedding bytes by hash."""
        if not hash_key or embedding is None:
            return False

        data_bytes = embedding.tobytes()

        # Always update memory cache
        self._memory_cache[hash_key] = data_bytes

        if self.redis_client:
            try:
                self.redis_client.set(f"face_emb:{hash_key}", data_bytes, ex=ttl_seconds)
                return True
            except Exception as e:
                logger.debug("Redis set failed, falling back to memory", error=str(e))

        return True

    def get_embedding(self, hash_key: str) -> Optional[np.ndarray]:
        """Retrieve embedding array by hash."""
        if not hash_key:
            return None

        # Check Redis first if available
        if self.redis_client:
            try:
                raw = self.redis_client.get(f"face_emb:{hash_key}")
                if raw:
                    return np.frombuffer(raw, dtype=np.float32)
            except Exception as e:
                logger.debug("Redis get failed", error=str(e))

        # Check memory cache fallback
        if hash_key in self._memory_cache:
            raw = self._memory_cache[hash_key]
            return np.frombuffer(raw, dtype=np.float32)

        return None
