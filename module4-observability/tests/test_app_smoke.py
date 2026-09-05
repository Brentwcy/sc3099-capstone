from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_logged_out_dashboard_renders_login_without_backend_access():
    app_path = Path(__file__).parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "SAIV Instructor Dashboard"
    assert len(app.get("form")) == 1
