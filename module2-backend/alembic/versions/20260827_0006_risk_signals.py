"""Create the risk signals table.

Revision ID: 20260827_0006
Revises: 20260825_0005
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_0006"
down_revision = "20260825_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("checkin_id", sa.String(length=36), nullable=False),
        sa.Column(
            "signal_type",
            sa.Enum(
                "geo_out_of_bounds",
                "impossible_travel",
                "geo_accuracy_low",
                "vpn_detected",
                "proxy_detected",
                "tor_detected",
                "suspicious_ip",
                "device_unknown",
                "device_emulator",
                "device_rooted",
                "attestation_failed",
                "rapid_succession",
                "unusual_time",
                "pattern_anomaly",
                "liveness_failed",
                "liveness_low_confidence",
                "deepfake_suspected",
                "replay_suspected",
                "face_match_failed",
                "face_match_low_confidence",
                name="risk_signal_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="risk_severity",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("weight", sa.Float(), server_default="0.1", nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_risk_signals_confidence",
        ),
        sa.CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="ck_risk_signals_weight",
        ),
        sa.ForeignKeyConstraint(
            ["checkin_id"], ["checkins.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_signals_checkin_id", "risk_signals", ["checkin_id"], unique=False
    )
    op.create_index(
        "ix_risk_signals_signal_type",
        "risk_signals",
        ["signal_type"],
        unique=False,
    )
    op.create_index(
        "ix_risk_signals_severity", "risk_signals", ["severity"], unique=False
    )
    op.create_index(
        "ix_risk_signals_detected_at", "risk_signals", ["detected_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_risk_signals_detected_at", table_name="risk_signals")
    op.drop_index("ix_risk_signals_severity", table_name="risk_signals")
    op.drop_index("ix_risk_signals_signal_type", table_name="risk_signals")
    op.drop_index("ix_risk_signals_checkin_id", table_name="risk_signals")
    op.drop_table("risk_signals")
