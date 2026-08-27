"""Create the initial devices table.

Revision ID: 20260821_0004
Revises: 20260821_0003
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0004"
down_revision = "20260821_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column(
            "platform",
            sa.Enum(
                "ios", "android", "web", "desktop", name="device_platform", native_enum=False
            ),
            nullable=True,
        ),
        sa.Column("browser", sa.String(length=100), nullable=True),
        sa.Column("os_version", sa.String(length=50), nullable=True),
        sa.Column("app_version", sa.String(length=50), nullable=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("public_key_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_key_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attestation_passed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_attestation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attestation_token", sa.Text(), nullable=True),
        sa.Column("is_trusted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "trust_score",
            sa.Enum("low", "medium", "high", name="device_trust_score", native_enum=False),
            server_default="low",
            nullable=False,
        ),
        sa.Column("is_emulator", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "is_rooted_jailbroken", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_checkins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("total_checkins >= 0", name="ck_devices_total_checkins"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_fingerprint"),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"], unique=False)
    op.create_index("ix_devices_is_active", "devices", ["is_active"], unique=False)
    op.create_index("ix_devices_is_trusted", "devices", ["is_trusted"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_devices_is_trusted", table_name="devices")
    op.drop_index("ix_devices_is_active", table_name="devices")
    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_table("devices")
