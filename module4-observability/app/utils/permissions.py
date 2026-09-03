"""Central role-to-page permissions for the Module 4 interface."""


ROLE_PAGE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "student": (
        "My Attendance",
        "Sessions",
    ),
    "ta": (
        "Sessions",
        "Check-ins",
        "Flagged Review",
    ),
    "instructor": (
        "Overview",
        "Sessions",
        "Check-ins",
        "Flagged Review",
        "Analytics",
        "Exports",
    ),
    "admin": (
        "Overview",
        "Audit Logs",
        "System Metrics",
    ),
}


def get_allowed_pages(role: str | None) -> tuple[str, ...]:
    """Return the explicitly permitted pages for a role."""
    return ROLE_PAGE_PERMISSIONS.get(role, ())


def resolve_page(role: str | None, requested_page: str | None) -> str | None:
    """Return an allowed page, falling back to the role's first page."""
    allowed_pages = get_allowed_pages(role)
    if not allowed_pages:
        return None
    if requested_page in allowed_pages:
        return requested_page
    return allowed_pages[0]
