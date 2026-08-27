"""Per-session authentication state helpers for the Streamlit dashboard."""

from collections.abc import Callable, Mapping
from time import monotonic
from typing import Any, TypeVar

import streamlit as st

from api_client import (
    APIClient,
    APIClientError,
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)


VALID_ROLES = frozenset({"student", "ta", "instructor", "admin"})
SESSION_VALIDATION_INTERVAL_SECONDS = 5 * 60
ResponseType = TypeVar("ResponseType")


class AuthStateError(ValueError):
    """Authentication data could not be stored safely."""


def initialize_auth_state() -> None:
    """Create logged-out defaults without replacing existing session values."""
    defaults = {
        "access_token": None,
        "refresh_token": None,
        "current_user": None,
        "role": None,
        "authenticated": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _validated_token_pair(payload: Mapping[str, Any]) -> tuple[str, str]:
    """Return a complete bearer token pair or reject the payload."""
    if not isinstance(payload, Mapping):
        raise AuthStateError("Authentication response must be an object")

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise AuthStateError("Authentication response has no access token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise AuthStateError("Authentication response has no refresh token")
    if payload.get("token_type") != "bearer":
        raise AuthStateError("Authentication response has an invalid token type")
    return access_token, refresh_token


def store_login_response(response: Mapping[str, Any]) -> None:
    """Validate and atomically store a successful login response."""
    try:
        access_token, refresh_token = _validated_token_pair(response)
        user = response.get("user")
        if not isinstance(user, Mapping):
            raise AuthStateError("Login response has no user object")

        role = user.get("role")
        if not isinstance(role, str) or role not in VALID_ROLES:
            raise AuthStateError("Login response has an invalid role")
        current_user = dict(user)
    except AuthStateError:
        clear_auth_state()
        raise

    st.session_state.update(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "current_user": current_user,
            "role": role,
            "authenticated": True,
        }
    )
    st.session_state.pop("_validated_access_token", None)
    st.session_state.pop("_profile_validated_at", None)


def replace_tokens(response: Mapping[str, Any]) -> None:
    """Atomically replace both tokens from a successful refresh response."""
    access_token, refresh_token = _validated_token_pair(response)
    st.session_state.update(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    )
    st.session_state.pop("_validated_access_token", None)
    st.session_state.pop("_profile_validated_at", None)


def clear_auth_state() -> None:
    """Reset every authentication key to its logged-out value."""
    st.session_state.update(
        {
            "access_token": None,
            "refresh_token": None,
            "current_user": None,
            "role": None,
            "authenticated": False,
        }
    )
    st.session_state.pop("_validated_access_token", None)
    st.session_state.pop("_profile_validated_at", None)


def authenticated_request(
    client: APIClient,
    operation: Callable[[str], ResponseType],
) -> ResponseType:
    """Run an access-token request, refreshing and retrying at most once."""
    access_token = st.session_state.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        clear_auth_state()
        raise AuthStateError("An access token is required")

    try:
        return operation(access_token)
    except APIResponseError as exc:
        if exc.status_code != 401:
            raise

    refresh_token = st.session_state.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        clear_auth_state()
        raise AuthStateError("A refresh token is required")

    try:
        refresh_response = client.refresh(refresh_token)
        replace_tokens(refresh_response)
    except (APIClientError, AuthStateError):
        clear_auth_state()
        raise

    try:
        return operation(st.session_state.access_token)
    except APIResponseError as exc:
        if exc.status_code == 401:
            clear_auth_state()
        raise


def _profile_validation_is_fresh() -> bool:
    """Return whether the backend profile was recently validated for this token."""
    access_token = st.session_state.get("access_token")
    validated_at = st.session_state.get("_profile_validated_at")
    current_user = st.session_state.get("current_user")
    role = st.session_state.get("role")
    if (
        st.session_state.get("_validated_access_token") != access_token
        or not isinstance(validated_at, (int, float))
        or not isinstance(current_user, Mapping)
        or role not in VALID_ROLES
        or current_user.get("role") != role
    ):
        return False
    age = monotonic() - validated_at
    return 0 <= age < SESSION_VALIDATION_INTERVAL_SECONDS


def validate_authenticated_session(client: APIClient) -> str | None:
    """Validate and update the current profile, returning a safe UI error if needed."""
    if _profile_validation_is_fresh():
        return None

    try:
        user = authenticated_request(client, client.get_current_user)
    except APIResponseError as exc:
        if exc.status_code == 401:
            clear_auth_state()
            return "Your session could not be validated. Please sign in again."
        if exc.status_code == 403:
            clear_auth_state()
            return "This account is disabled or unavailable. Please sign in again."
        if exc.status_code == 429:
            message = "Session validation is temporarily rate limited."
            if exc.retry_after:
                message += f" Retry after: {exc.retry_after}."
            return message
        if exc.status_code == 503:
            return "The backend is temporarily unavailable. Please try again later."
        return "The session could not be validated right now. Please try again later."
    except APITimeoutError:
        return "Session validation timed out. Please try again later."
    except APIConnectionError:
        return "The backend is currently unreachable. Please try again later."
    except AuthStateError:
        clear_auth_state()
        return "Your session is no longer valid. Please sign in again."
    except APIClientError:
        clear_auth_state()
        return "The authentication service returned an invalid response. Please sign in again."

    if not isinstance(user, Mapping):
        clear_auth_state()
        return "The authentication service returned an invalid profile. Please sign in again."

    role = user.get("role")
    if not isinstance(role, str) or role not in VALID_ROLES:
        clear_auth_state()
        return "The authentication service returned an invalid profile. Please sign in again."

    st.session_state.current_user = dict(user)
    st.session_state.role = role
    st.session_state["_validated_access_token"] = st.session_state.access_token
    st.session_state["_profile_validated_at"] = monotonic()
    return None


def _login_error_message(error: APIResponseError) -> str:
    """Return a safe login message for a backend HTTP error."""
    if error.status_code == 401:
        return "Invalid email or password."
    if error.status_code == 403:
        return "This account is disabled or unavailable."
    if error.status_code == 422:
        return "Please enter a valid email address and password."
    if error.status_code == 429:
        message = "Too many login attempts. Please try again later."
        if error.retry_after:
            message += f" Retry after: {error.retry_after}."
        return message
    if error.status_code == 503:
        return "The authentication service is temporarily unavailable."
    return "Authentication failed. Please try again."


def render_login(client: APIClient) -> None:
    """Render the login form and store a successful backend response."""
    st.title("SAIV Dashboard")
    st.subheader("Sign in")

    with st.form("login-form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if not submitted:
        return

    clear_auth_state()
    email = email.strip()
    if not email or not password:
        st.error("Enter both your email address and password.")
        return

    try:
        response = client.login(email, password)
        store_login_response(response)
    except APIResponseError as exc:
        st.error(_login_error_message(exc))
        return
    except APITimeoutError:
        st.error("The authentication request timed out. Please try again.")
        return
    except APIConnectionError:
        st.error("The backend is currently unreachable. Please try again later.")
        return
    except APIClientError:
        st.error("Authentication could not be completed. Please try again.")
        return
    except AuthStateError:
        st.error("The authentication service returned an invalid response.")
        return

    st.rerun()
