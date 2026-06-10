"""Domain tables for Reference, Catalog, and Loan bounded contexts.

Revision ID: 002
Revises: 001
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loan_rule_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("max_active_loans", sa.Integer(), nullable=False),
        sa.Column("loan_period_days", sa.Integer(), nullable=False),
        sa.Column("calendar_policy", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "patron_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("loan_rule_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["loan_rule_set_id"], ["loan_rule_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "class_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade", sa.String(length=32), nullable=False),
        sa.Column("section", sa.String(length=32), nullable=False),
        sa.Column("academic_year", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grade", "section", "academic_year", name="uq_class_section"),
    )

    op.create_table(
        "patrons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("patron_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("card_barcode", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_section_id"], ["class_sections.id"]),
        sa.ForeignKeyConstraint(["patron_type_id"], ["patron_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_ref"),
        sa.UniqueConstraint("card_barcode"),
    )

    op.create_table(
        "patron_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patron_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["patron_id"], ["patrons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "catalogs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("subtitle", sa.String(length=512), nullable=True),
        sa.Column("isbn", sa.String(length=20), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("subject_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("call_number", sa.String(length=64), nullable=True),
        sa.Column("ddc", sa.String(length=32), nullable=True),
        sa.Column("cataloging_status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("accession_number", sa.String(length=64), nullable=False),
        sa.Column("shelf_location", sa.String(length=128), nullable=True),
        sa.Column("holding_status", sa.String(length=32), nullable=False),
        sa.Column("circulating", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["catalog_id"], ["catalogs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barcode"),
        sa.UniqueConstraint("accession_number"),
    )

    op.create_table(
        "loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patron_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("holding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_rule_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("checkout_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkout_operator_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"]),
        sa.ForeignKeyConstraint(["loan_rule_set_id"], ["loan_rule_sets.id"]),
        sa.ForeignKeyConstraint(["patron_id"], ["patrons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "uq_loan_open_holding",
        "loans",
        ["holding_id"],
        unique=True,
        postgresql_where=sa.text("returned_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_loan_open_holding", table_name="loans")
    op.drop_table("loans")
    op.drop_table("holdings")
    op.drop_table("catalogs")
    op.drop_table("patron_blocks")
    op.drop_table("patrons")
    op.drop_table("class_sections")
    op.drop_table("patron_types")
    op.drop_table("loan_rule_sets")
