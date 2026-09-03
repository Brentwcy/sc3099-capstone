"""Tests for project-level Streamlit behavior."""

from pathlib import Path
import tomllib
import unittest


MODULE_ROOT = Path(__file__).resolve().parents[1]


class StreamlitConfigTests(unittest.TestCase):
    def test_native_sidebar_navigation_is_disabled(self) -> None:
        config_path = MODULE_ROOT / ".streamlit" / "config.toml"

        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)

        self.assertIs(config["client"]["showSidebarNavigation"], False)


if __name__ == "__main__":
    unittest.main()
