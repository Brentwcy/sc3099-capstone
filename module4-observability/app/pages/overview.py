"""Compatibility entry point for the role-specific Admin overview."""

from typing import Any

from pages.admin_overview import render_admin_overview


def render_overview(current_user: dict[str, Any]) -> None:
    """Render the current Admin overview for older callers."""
    render_admin_overview(current_user)
