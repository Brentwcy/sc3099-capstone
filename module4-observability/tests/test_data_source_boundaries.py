"""Architecture tests for live dashboard data-source boundaries."""

from __future__ import annotations

import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"


class DataSourceBoundaryTests(unittest.TestCase):
    def test_live_role_pages_do_not_import_mock_data(self) -> None:
        for page_name in (
            "student_attendance.py",
            "instructor_overview.py",
            "admin_overview.py",
        ):
            with self.subTest(page_name=page_name):
                source = (APP_DIR / "pages" / page_name).read_text(encoding="utf-8")
                self.assertNotIn("mock_data", source)
                self.assertNotIn("MOCK_", source)

    def test_no_live_page_defines_mock_references(self) -> None:
        files_with_mock_references = {
            path.relative_to(APP_DIR).as_posix()
            for path in APP_DIR.rglob("*.py")
            if "MOCK_" in path.read_text(encoding="utf-8")
        }

        self.assertEqual(
            files_with_mock_references,
            {
                "utils/mock_data.py",
            },
        )

    def test_ta_discovery_uses_the_backend_safe_endpoint_without_course_scoping(self) -> None:
        source = (APP_DIR / "pages" / "sessions.py").read_text(encoding="utf-8")

        self.assertIn("client.get_my_sessions", source)
        self.assertIn("no per-TA course assignment model", source)
        self.assertNotIn("ta_course", source)


if __name__ == "__main__":
    unittest.main()
