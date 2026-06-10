"""Circulation fulfillment for delivery / pick-up (ADR-022).

Revision ID: 004
Revises: 003
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "circulation_fulfillments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("holding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("destination_notes", sa.String(length=512), nullable=True),
        sa.Column(
            "destination_class_section_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("destination_contact", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"]),
        sa.ForeignKeyConstraint(["loan_id"], ["loans.id"]),
        sa.ForeignKeyConstraint(["destination_class_section_id"], ["class_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_circulation_fulfillments_loan_id",
        "circulation_fulfillments",
        ["loan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_circulation_fulfillments_loan_id", table_name="circulation_fulfillments")
    op.drop_table("circulation_fulfillments")
