"""Minimal HTTP client skeleton for the Module 2 backend."""

from typing import Any

import requests

from config import BACKEND_URL


class APIClient:
    """Small unauthenticated client that can grow with later project work."""

    def __init__(self, base_url: str = BACKEND_URL, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str) -> requests.Response:
        """Send a basic GET request to the backend."""
        return requests.get(
            f"{self.base_url}/{path.lstrip('/')}",
            timeout=self.timeout,
        )

    def check_health(self) -> dict[str, Any]:
        """Check the public Module 2 health endpoint without authentication."""
        try:
            response = self.get("/health")
            try:
                payload: Any = response.json()
            except requests.exceptions.JSONDecodeError:
                payload = {"status": "invalid response"}

            return {
                "reachable": True,
                "healthy": response.ok,
                "status_code": response.status_code,
                "data": payload,
            }
        except requests.RequestException as exc:
            return {
                "reachable": False,
                "healthy": False,
                "status_code": None,
                "data": {},
                "error": str(exc),
            }
