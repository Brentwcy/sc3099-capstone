"""Small dependency fakes used by the Module 4 unit tests."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SessionState(dict[str, Any]):
    """Dictionary with Streamlit-style attribute access."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


class FakeForm:
    """No-op context manager returned by ``st.form``."""

    def __enter__(self) -> FakeForm:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class FakeSidebar:
    """Record the small sidebar surface used by the application."""

    def __init__(self, streamlit_module: FakeStreamlit) -> None:
        self.streamlit = streamlit_module
        self.logout_clicked = False
        self.radio_options: tuple[str, ...] | None = None
        self.events: list[tuple[str, Any]] = []

    def reset(self) -> None:
        self.logout_clicked = False
        self.radio_options = None
        self.events.clear()

    def title(self, value: str) -> None:
        self.events.append(("title", value))

    def caption(self, value: str) -> None:
        self.events.append(("caption", value))

    def button(self, label: str, **kwargs: Any) -> bool:
        self.events.append(("button", (label, kwargs)))
        return self.logout_clicked

    def error(self, value: str) -> None:
        self.events.append(("error", value))

    def radio(self, label: str, options: tuple[str, ...], *, key: str) -> str:
        self.radio_options = tuple(options)
        self.events.append(("radio", (label, key)))
        if self.streamlit.session_state.get(key) not in options:
            self.streamlit.session_state[key] = options[0]
        return self.streamlit.session_state[key]


class FakeStreamlit(ModuleType):
    """Minimal Streamlit module supporting auth and routing tests."""

    def __init__(self) -> None:
        super().__init__("streamlit")
        self.session_state = SessionState()
        self.sidebar = FakeSidebar(self)
        self.input_values: dict[str, str] = {}
        self.input_calls: list[tuple[str, dict[str, Any]]] = []
        self.form_submitted = False
        self.errors: list[str] = []
        self.titles: list[str] = []
        self.subheaders: list[str] = []
        self.rerun_count = 0
        self.page_config: dict[str, Any] = {}

    def reset(self) -> None:
        self.session_state.clear()
        self.sidebar.reset()
        self.input_values.clear()
        self.input_calls.clear()
        self.form_submitted = False
        self.errors.clear()
        self.titles.clear()
        self.subheaders.clear()
        self.rerun_count = 0

    def set_page_config(self, **kwargs: Any) -> None:
        self.page_config = kwargs

    def title(self, value: str) -> None:
        self.titles.append(value)

    def subheader(self, value: str) -> None:
        self.subheaders.append(value)

    def form(self, key: str) -> FakeForm:
        return FakeForm()

    def text_input(self, label: str, **kwargs: Any) -> str:
        self.input_calls.append((label, kwargs))
        return self.input_values.get(label, "")

    def form_submit_button(self, label: str) -> bool:
        return self.form_submitted

    def error(self, value: str) -> None:
        self.errors.append(value)

    def rerun(self) -> None:
        self.rerun_count += 1


class FakeRequestException(Exception):
    """Base fake for requests transport exceptions."""


class FakeTimeout(FakeRequestException):
    """Fake requests timeout."""


class FakeConnectionError(FakeRequestException):
    """Fake requests connection error."""


class FakeJSONDecodeError(ValueError):
    """Fake requests JSON decoding error."""


class FakeResponse:
    """Small requests.Response replacement."""

    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        *,
        headers: dict[str, str] | None = None,
        text: str = "",
        reason: str = "",
    ) -> None:
        self.status_code = status_code
        self.payload = {} if payload is None else payload
        self.headers = headers or {}
        self.text = text
        self.reason = reason

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeRequests(ModuleType):
    """Queue-backed requests module that records exact calls."""

    def __init__(self) -> None:
        super().__init__("requests")
        self.Timeout = FakeTimeout
        self.ConnectionError = FakeConnectionError
        self.RequestException = FakeRequestException
        self.exceptions = SimpleNamespace(JSONDecodeError=FakeJSONDecodeError)
        self.Response = FakeResponse
        self.calls: list[dict[str, Any]] = []
        self.actions: list[FakeResponse | Exception] = []

    def reset(self) -> None:
        self.calls.clear()
        self.actions.clear()

    def queue(self, *actions: FakeResponse | Exception) -> None:
        self.actions.extend(actions)

    def request(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        action: FakeResponse | Exception
        action = self.actions.pop(0) if self.actions else FakeResponse()
        if isinstance(action, Exception):
            raise action
        return action


fake_streamlit = FakeStreamlit()
fake_requests = FakeRequests()
sys.modules["streamlit"] = fake_streamlit
sys.modules["requests"] = fake_requests


def login_payload(role: str = "instructor") -> dict[str, Any]:
    """Return a complete successful login response."""
    return {
        "access_token": "access-old",
        "refresh_token": "refresh-old",
        "token_type": "bearer",
        "user": {
            "id": "user-id",
            "email": f"{role}@example.com",
            "role": role,
        },
    }


def set_authenticated(role: str = "instructor") -> None:
    """Populate the fake session with a complete authenticated state."""
    fake_streamlit.session_state.update(
        {
            "access_token": "access-old",
            "refresh_token": "refresh-old",
            "current_user": {
                "id": "user-id",
                "email": f"{role}@example.com",
                "role": role,
            },
            "role": role,
            "authenticated": True,
        }
    )
