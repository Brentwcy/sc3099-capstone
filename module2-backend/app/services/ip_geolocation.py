import ipaddress
from typing import Protocol
from urllib.parse import quote

import httpx
from fastapi import Depends, Request

from app.core.config import Settings, get_settings


# National bounds include Singapore's outlying islands as well as the main island.
SINGAPORE_MIN_LATITUDE = 1.13
SINGAPORE_MAX_LATITUDE = 1.48
SINGAPORE_MIN_LONGITUDE = 103.60
SINGAPORE_MAX_LONGITUDE = 104.10


class IPCountryLookupError(Exception):
    """Raised when a public IP's country cannot be established safely."""


class IPCountryResolver(Protocol):
    async def country_code(self, ip_address: str) -> str: ...


class HttpIPCountryResolver:
    """Resolve public IPs to ISO 3166-1 alpha-2 country codes."""

    def __init__(
        self,
        *,
        url_template: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url_template = url_template
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds)
        )

    async def country_code(self, ip_address: str) -> str:
        url = self._url_template.format(ip=quote(ip_address, safe=""))
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise IPCountryLookupError("Public IP country lookup failed") from exc

        country_code = response.text.strip().upper()
        if len(country_code) != 2 or not country_code.isalpha():
            raise IPCountryLookupError("Public IP country lookup returned invalid data")
        return country_code

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def coordinates_are_in_singapore(latitude: float, longitude: float) -> bool:
    return (
        SINGAPORE_MIN_LATITUDE <= latitude <= SINGAPORE_MAX_LATITUDE
        and SINGAPORE_MIN_LONGITUDE <= longitude <= SINGAPORE_MAX_LONGITUDE
    )


def client_ip_from_request(
    request: Request,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for is not None:
        first_address = forwarded_for.split(",", maxsplit=1)[0].strip()
        if not first_address:
            raise ValueError("X-Forwarded-For does not contain a client IP")
        return ipaddress.ip_address(first_address)

    socket_host = request.client.host if request.client is not None else None
    if not socket_host:
        return None
    try:
        return ipaddress.ip_address(socket_host)
    except ValueError:
        # ASGI test clients and local development servers may expose a hostname
        # rather than an address. Treat that the same way as a local socket.
        return None


_http_ip_country_resolver: HttpIPCountryResolver | None = None


def get_ip_country_resolver(
    settings: Settings = Depends(get_settings),
) -> IPCountryResolver:
    global _http_ip_country_resolver
    if _http_ip_country_resolver is None:
        _http_ip_country_resolver = HttpIPCountryResolver(
            url_template=settings.ip_country_lookup_url,
            timeout_seconds=settings.ip_country_lookup_timeout_seconds,
        )
    return _http_ip_country_resolver


async def close_ip_country_resolver() -> None:
    global _http_ip_country_resolver
    if _http_ip_country_resolver is not None:
        await _http_ip_country_resolver.aclose()
        _http_ip_country_resolver = None
