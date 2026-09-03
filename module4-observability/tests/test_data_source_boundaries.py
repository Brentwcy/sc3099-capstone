"""Architecture tests for the explicit Week 3 live-versus-mock boundary."""

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

    def test_only_ta_discovery_and_its_fixture_define_mock_references(self) -> None:
        files_with_mock_references = {
            path.relative_to(APP_DIR).as_posix()
            for path in APP_DIR.rglob("*.py")
            if "MOCK_" in path.read_text(encoding="utf-8")
        }

        self.assertEqual(
            files_with_mock_references,
            {
                "pages/ta_sessions.py",
                "utils/mock_data.py",
            },
        )

    def test_ta_discovery_source_is_explicitly_labelled(self) -> None:
        source = (APP_DIR / "pages" / "ta_sessions.py").read_text(encoding="utf-8")

        self.assertIn("Development session list", source)
        self.assertIn("live TA session discovery is not yet available", source)
        self.assertIn("get_ta_session_options", source)


if __name__ == "__main__":
    unittest.main()
