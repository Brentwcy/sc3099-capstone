import httpx
import pytest

from app.services.ip_geolocation import HttpIPCountryResolver, IPCountryLookupError


@pytest.mark.asyncio
async def test_http_country_resolver_returns_valid_iso_country_code():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://geo.example/119.81.44.63/country/"
        return httpx.Response(200, text="sg\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolver = HttpIPCountryResolver(
            url_template="https://geo.example/{ip}/country/",
            timeout_seconds=1,
            client=client,
        )
        assert await resolver.country_code("119.81.44.63") == "SG"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body"),
    [(503, "SG"), (200, "not-a-country-code")],
)
async def test_http_country_resolver_rejects_failed_or_invalid_responses(
    status_code,
    body,
):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(status_code, text=body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        resolver = HttpIPCountryResolver(
            url_template="https://geo.example/{ip}/country/",
            timeout_seconds=1,
            client=client,
        )
        with pytest.raises(IPCountryLookupError):
            await resolver.country_code("8.8.8.8")
