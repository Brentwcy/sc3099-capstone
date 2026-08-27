"""Page routing for the Week 1 dashboard shell."""

from typing import Any

from pages.overview import render_overview
from pages.shells import render_shell


def render_page(page_name: str, current_user: dict[str, Any]) -> None:
    """Render the selected page without applying role-based filtering."""
    if page_name == "Overview":
        render_overview(current_user)
    else:
        render_shell(page_name)
