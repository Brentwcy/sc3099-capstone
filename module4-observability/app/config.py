"""Environment-backed configuration for Module 4."""

import os


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
