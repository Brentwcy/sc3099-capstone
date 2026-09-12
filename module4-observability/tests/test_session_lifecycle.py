"""Focused tests for Week 4 Instructor lifecycle and deletion controls."""

from __future__ import annotations

import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIResponseError  # noqa: E402
from pages import session_actions  # noqa: E402


def authoritative_detail(status: str) -> dict[str, Any]:
    return {"id": "session-1", "status": status}


class LifecycleClient:
    def __init__(
        self,
        *,
        update_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.update_error = update_error
        self.delete_error = delete_error
        self.update_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.delete_calls: list[tuple[str, str]] = []

    def update_session(
        self,
        access_token: str,
        session_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.update_calls.append((access_token, session_id, payload))
        if self.update_error is not None:
            raise self.update_error
        return authoritative_detail(str(payload["status"]))

    def delete_session(self, access_token: str, session_id: str) -> None:
        self.delete_calls.append((access_token, session_id))
        if self.delete_error is not None:
            raise self.delete_error


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("instructor")

    def _ui_patches(
        self,
        *,
        clicked_label: str | None = None,
        delete_confirmed: bool = False,
    ) -> tuple[ExitStack, MagicMock, MagicMock, MagicMock, MagicMock]:
        stack = ExitStack()
        button = stack.enter_context(
            patch.object(
                session_actions.st,
                "button",
                side_effect=lambda label, **_kwargs: label == clicked_label,
                create=True,
            )
        )
        checkbox = stack.enter_context(
            patch.object(
                session_actions.st,
                "checkbox",
                return_value=delete_confirmed,
                create=True,
            )
        )
        warning = stack.enter_context(
            patch.object(session_actions.st, "warning", create=True)
        )
        success = stack.enter_context(
            patch.object(session_actions.st, "success", create=True)
        )
        stack.enter_context(
            patch.object(
                session_actions,
                "loading_state",
                return_value=nullcontext(),
            )
        )
        return stack, button, checkbox, warning, success

    def _rendered_button_labels(self, status: str) -> list[str]:
        client = LifecycleClient()
        stack, button, _checkbox, _warning, _success = self._ui_patches()
        with stack:
            session_actions.render_session_actions(
                client,
                authoritative_detail(status),
            )
        return [call.args[0] for call in button.call_args_list]

    def test_scheduled_offers_activate_cancel_and_delete(self) -> None:
        self.assertEqual(
            self._rendered_button_labels("scheduled"),
            ["Activate Session", "Cancel Session", "Delete Session"],
        )

    def test_active_offers_close_and_cancel_only(self) -> None:
        self.assertEqual(
            self._rendered_button_labels("active"),
            ["Close Session", "Cancel Session"],
        )

    def test_closed_offers_cancel_only(self) -> None:
        self.assertEqual(
            self._rendered_button_labels("closed"),
            ["Cancel Session"],
        )

    def test_cancelled_offers_no_mutation_controls(self) -> None:
        self.assertEqual(self._rendered_button_labels("cancelled"), [])

    def test_ta_and_admin_are_explicitly_blocked_from_all_actions(self) -> None:
        for role in ("ta", "admin"):
            with self.subTest(role=role):
                fake_streamlit.reset()
                set_authenticated(role)
                client = LifecycleClient()
                stack, button, checkbox, warning, _success = self._ui_patches(
                    clicked_label="Activate Session",
                    delete_confirmed=True,
                )
                with stack:
                    changed = session_actions.render_session_actions(
                        client,
                        authoritative_detail("scheduled"),
                    )

                self.assertFalse(changed)
                button.assert_not_called()
                checkbox.assert_not_called()
                warning.assert_not_called()
                self.assertEqual(client.update_calls, [])
                self.assertEqual(client.delete_calls, [])

    def test_each_lifecycle_action_sends_only_target_status_and_reruns(self) -> None:
        cases = (
            ("scheduled", "Activate Session", "active"),
            ("active", "Close Session", "closed"),
            ("scheduled", "Cancel Session", "cancelled"),
        )
        for current_status, clicked_label, target_status in cases:
            with self.subTest(action=clicked_label):
                fake_streamlit.rerun_count = 0
                client = LifecycleClient()
                stack, _button, _checkbox, _warning, success = self._ui_patches(
                    clicked_label=clicked_label
                )
                with stack:
                    changed = session_actions.render_session_actions(
                        client,
                        authoritative_detail(current_status),
                    )

                self.assertTrue(changed)
                self.assertEqual(
                    client.update_calls,
                    [("access-old", "session-1", {"status": target_status})],
                )
                success.assert_called_once_with(
                    session_actions.LIFECYCLE_SUCCESS_MESSAGES[target_status]
                )
                self.assertEqual(fake_streamlit.rerun_count, 1)

    def test_delete_requires_confirmation_before_api_call(self) -> None:
        client = LifecycleClient()
        stack, _button, _checkbox, _warning, _success = self._ui_patches(
            clicked_label="Delete Session",
            delete_confirmed=False,
        )
        with stack:
            changed = session_actions.render_session_actions(
                client,
                authoritative_detail("scheduled"),
            )

        self.assertFalse(changed)
        self.assertEqual(client.delete_calls, [])

    def test_successful_delete_clears_selection_and_reruns(self) -> None:
        fake_streamlit.session_state[session_actions.SESSION_SELECTION_KEY] = (
            "stale selection"
        )
        confirmation_key = "delete_session_confirmed_session-1"
        fake_streamlit.session_state[confirmation_key] = True
        client = LifecycleClient()
        stack, _button, _checkbox, _warning, success = self._ui_patches(
            clicked_label="Delete Session",
            delete_confirmed=True,
        )
        with stack:
            changed = session_actions.render_session_actions(
                client,
                authoritative_detail("scheduled"),
            )

        self.assertTrue(changed)
        self.assertEqual(client.delete_calls, [("access-old", "session-1")])
        self.assertNotIn(
            session_actions.SESSION_SELECTION_KEY,
            fake_streamlit.session_state,
        )
        self.assertNotIn(confirmation_key, fake_streamlit.session_state)
        success.assert_called_once_with("Session deleted successfully.")
        self.assertEqual(fake_streamlit.rerun_count, 1)

    def test_lifecycle_api_failure_uses_shared_error_renderer(self) -> None:
        failure = APIResponseError(status_code=400, detail="private backend rule")
        client = LifecycleClient(update_error=failure)
        stack, _button, _checkbox, _warning, _success = self._ui_patches(
            clicked_label="Activate Session"
        )
        api_error = stack.enter_context(
            patch.object(session_actions, "render_api_error")
        )
        with stack:
            changed = session_actions.render_session_actions(
                client,
                authoritative_detail("scheduled"),
            )

        self.assertFalse(changed)
        api_error.assert_called_once_with(failure)
        self.assertEqual(fake_streamlit.rerun_count, 0)

    def test_delete_api_failure_uses_shared_error_and_keeps_selection(self) -> None:
        failure = APIResponseError(status_code=409, detail="private backend rule")
        fake_streamlit.session_state[session_actions.SESSION_SELECTION_KEY] = (
            "current selection"
        )
        client = LifecycleClient(delete_error=failure)
        stack, _button, _checkbox, _warning, _success = self._ui_patches(
            clicked_label="Delete Session",
            delete_confirmed=True,
        )
        api_error = stack.enter_context(
            patch.object(session_actions, "render_api_error")
        )
        with stack:
            changed = session_actions.render_session_actions(
                client,
                authoritative_detail("scheduled"),
            )

        self.assertFalse(changed)
        api_error.assert_called_once_with(failure)
        self.assertEqual(
            fake_streamlit.session_state[session_actions.SESSION_SELECTION_KEY],
            "current selection",
        )
        self.assertEqual(fake_streamlit.rerun_count, 0)

    def test_no_admin_status_override_endpoint_is_introduced(self) -> None:
        app_root = Path(session_actions.__file__).parents[1]
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in app_root.rglob("*.py")
        )

        self.assertNotIn("/api/v1/admin/sessions/", source)


if __name__ == "__main__":
    unittest.main()
