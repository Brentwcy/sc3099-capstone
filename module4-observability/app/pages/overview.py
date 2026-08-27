"""Minimal mock-data Overview page for Week 1."""

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import APIClient
from config import BACKEND_URL
from utils.mock_data import MOCK_CHECKINS, MOCK_OVERVIEW_STATS


def render_overview(current_user: dict[str, Any]) -> None:
    """Render the Week 1 overview using only mock dashboard data."""
    st.title("SAIV Dashboard")
    st.caption(
        f"Mock user: {current_user['full_name']} ({current_user['role']}) — "
        "authentication and RBAC are not enabled."
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric("Total sessions", MOCK_OVERVIEW_STATS["total_sessions"])
    metric_columns[1].metric("Active sessions", MOCK_OVERVIEW_STATS["active_sessions"])
    metric_columns[2].metric("Today's check-ins", MOCK_OVERVIEW_STATS["total_checkins_today"])
    metric_columns[3].metric(
        "Approval rate",
        f"{MOCK_OVERVIEW_STATS['approval_rate']:.0%}",
    )

    left_column, right_column = st.columns([2, 1])

    with left_column:
        st.subheader("Recent check-ins")
        checkins = pd.DataFrame(MOCK_CHECKINS)
        display_columns = [
            "checked_in_at",
            "student_name",
            "session_name",
            "status",
            "risk_score",
        ]
        st.dataframe(
            checkins[display_columns],
            hide_index=True,
            use_container_width=True,
        )

    with right_column:
        st.subheader("Check-ins by day")
        trend_data = pd.DataFrame(MOCK_OVERVIEW_STATS["trends"]["checkins_by_day"])
        chart = px.bar(
            trend_data,
            x="date",
            y="count",
            labels={"date": "Date", "count": "Check-ins"},
        )
        chart.update_layout(showlegend=False)
        st.plotly_chart(chart, use_container_width=True)

    st.subheader("Module 2 connectivity")
    st.caption(f"Backend health endpoint: {BACKEND_URL}/health")
    with st.form("backend-health-form"):
        check_health = st.form_submit_button("Check backend health")

    if check_health:
        result = APIClient().check_health()
        if result["healthy"]:
            st.success(
                f"Module 2 is reachable (HTTP {result['status_code']}): "
                f"{result['data']}"
            )
        elif result["reachable"]:
            st.warning(
                f"Module 2 responded with HTTP {result['status_code']}: "
                f"{result['data']}"
            )
        else:
            st.error(f"Module 2 is unavailable: {result['error']}")
