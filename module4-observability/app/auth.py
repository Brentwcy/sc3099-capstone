from __future__ import annotations

from typing import Any, MutableMapping

from app.api_client import APIClient, APIClientError, AuthorizationError


DASHBOARD_ROLES = frozenset({"ta", "instructor", "admin"})
AUTH_KEYS = ("access_token", "refresh_token", "current_user")


def initialize_auth_state(state: MutableMapping[str, Any]) -> None:
    for key in AUTH_KEYS:
        state.setdefault(key, None)


def clear_auth_state(state: MutableMapping[str, Any]) -> None:
    for key in AUTH_KEYS:
        state[key] = None


def login_dashboard(
    state: MutableMapping[str, Any],
    client: APIClient,
    *,
    email: str,
    password: str,
) -> dict[str, Any]:
    result = client.login(email, password)
    user = result["user"]
    if user.get("role") not in DASHBOARD_ROLES:
        # The backend remains the authorization authority. This is a UX gate only.
        try:
            client.logout(result["access_token"])
        except APIClientError:
            pass
        finally:
            clear_auth_state(state)
        raise AuthorizationError("The instructor dashboard is restricted to TA, instructor, and admin roles.")

    state["access_token"] = result["access_token"]
    state["refresh_token"] = result.get("refresh_token")
    state["current_user"] = user
    return user


def logout_dashboard(state: MutableMapping[str, Any], client: APIClient) -> None:
    token = state.get("access_token")
    try:
        if token:
            client.logout(token)
    finally:
        clear_auth_state(state)
