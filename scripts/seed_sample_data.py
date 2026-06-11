#!/usr/bin/env python3
"""Load MVP sample data into PostgreSQL (idempotent).

Uses fixed seed UUIDs from scripts/sql/002_sample_data.sql.
Safe to re-run: skips rows that already exist.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

# Allow running as scripts/seed_sample_data.py without install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus  # noqa: E402
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel  # noqa: E402
from lms.config import get_settings  # noqa: E402
from lms.loan.infrastructure.models.models import LoanModel, LoanRuleSetModel  # noqa: E402
from lms.reference.domain.enums import PatronStatus  # noqa: E402
from lms.reference.infrastructure.models.models import (  # noqa: E402
    ClassSectionModel,
    PatronModel,
    PatronTypeModel,
)
from lms.shared.application.seed_api_users import (  # noqa: E402
    DEFAULT_DEV_PASSWORD,
    ensure_default_api_users,
)
from lms.shared.db.session import SessionLocal  # noqa: E402

# Fixed seed IDs (match scripts/sql/002_sample_data.sql)
RULE_STUDENT = uuid.UUID("00000001-0001-4001-8001-000000000001")
RULE_TEACHER = uuid.UUID("00000001-0001-4001-8001-000000000002")
TYPE_STUDENT = uuid.UUID("00000002-0001-4001-8001-000000000001")
TYPE_TEACHER = uuid.UUID("00000002-0001-4001-8001-000000000002")
SEC_7A = uuid.UUID("00000003-0001-4001-8001-000000000001")
SEC_8B = uuid.UUID("00000003-0001-4001-8001-000000000002")
SEC_9C = uuid.UUID("00000003-0001-4001-8001-000000000003")
PAT_ARJUN = uuid.UUID("00000004-0001-4001-8001-000000000001")
PAT_PRIYA = uuid.UUID("00000004-0001-4001-8001-000000000002")
PAT_ROHAN = uuid.UUID("00000004-0001-4001-8001-000000000003")
PAT_KAVITA = uuid.UUID("00000004-0001-4001-8001-000000000004")
PAT_SNEHA = uuid.UUID("00000004-0001-4001-8001-000000000005")
CAT_MATH = uuid.UUID("00000005-0001-4001-8001-000000000001")
CAT_PAN = uuid.UUID("00000005-0001-4001-8001-000000000002")
CAT_NEHRU = uuid.UUID("00000005-0001-4001-8001-000000000003")
CAT_DRAFT = uuid.UUID("00000005-0001-4001-8001-000000000004")
HLD_MATH1 = uuid.UUID("00000006-0001-4001-8001-000000000001")
HLD_MATH2 = uuid.UUID("00000006-0001-4001-8001-000000000002")
HLD_MATH3 = uuid.UUID("00000006-0001-4001-8001-000000000003")
HLD_PAN1 = uuid.UUID("00000006-0001-4001-8001-000000000004")
HLD_NEHRU = uuid.UUID("00000006-0001-4001-8001-000000000005")
HLD_PAN2 = uuid.UUID("00000006-0001-4001-8001-000000000006")
LOAN_OPEN = uuid.UUID("00000007-0001-4001-8001-000000000001")
LOAN_CLOSED = uuid.UUID("00000007-0001-4001-8001-000000000002")
LOAN_OVERDUE = uuid.UUID("00000007-0001-4001-8001-000000000003")


def _add_if_missing(session, model, pk: uuid.UUID, **fields) -> bool:
    if session.get(model, pk) is not None:
        return False
    session.add(model(id=pk, **fields))
    return True


SEED_BARCODES = (
    "BC-MATH7-001",
    "BC-MATH7-002",
    "BC-MATH7-003",
    "BC-PAN-001",
    "BC-NEH-001",
    "BC-PAN-002",
)
SEED_CARD_BARCODES = ("LIB-7001", "LIB-7002", "LIB-8001", "LIB-T101", "LIB-9001")
SEED_EXTERNAL_REFS = (
    "ADM-2025-7001",
    "ADM-2025-7002",
    "ADM-2025-8001",
    "STF-2025-0101",
    "ADM-2025-9001",
)


def _clear_seed_namespace(session) -> None:
    from sqlalchemy import text

    for bc in SEED_BARCODES:
        session.execute(
            text(
                "DELETE FROM loans WHERE holding_id IN "
                "(SELECT id FROM holdings WHERE barcode = :bc)"
            ),
            {"bc": bc},
        )
        session.execute(text("DELETE FROM holdings WHERE barcode = :bc"), {"bc": bc})

    session.execute(
        text(
            """
            DELETE FROM circulation_fulfillments
            WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-'
               OR holding_id::text ~ '^0000000[0-9]-0001-4001-8001-'
               OR loan_id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM loans
            WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-'
               OR holding_id::text ~ '^0000000[0-9]-0001-4001-8001-'
               OR patron_id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM patron_blocks WHERE patron_id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM holdings WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM catalogs WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM patrons WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM class_sections WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM patron_types WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';
            DELETE FROM loan_rule_sets WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';
            """
        )
    )

    for card in SEED_CARD_BARCODES:
        session.execute(text("DELETE FROM patrons WHERE card_barcode = :v"), {"v": card})
    for ref in SEED_EXTERNAL_REFS:
        session.execute(text("DELETE FROM patrons WHERE external_ref = :v"), {"v": ref})
    session.execute(text("DELETE FROM patron_types WHERE code IN ('STUDENT', 'TEACHER')"))


def seed(session) -> dict[str, int]:
    stats = {"inserted": 0, "skipped": 0}

    def track(added: bool) -> None:
        if added:
            stats["inserted"] += 1
        else:
            stats["skipped"] += 1

    _clear_seed_namespace(session)
    session.flush()

    track(
        _add_if_missing(
            session,
            LoanRuleSetModel,
            RULE_STUDENT,
            name="Student standard",
            max_active_loans=5,
            loan_period_days=14,
            calendar_policy="CALENDAR_DAYS",
        )
    )
    track(
        _add_if_missing(
            session,
            LoanRuleSetModel,
            RULE_TEACHER,
            name="Teacher standard",
            max_active_loans=10,
            loan_period_days=30,
            calendar_policy="CALENDAR_DAYS",
        )
    )

    track(
        _add_if_missing(
            session,
            PatronTypeModel,
            TYPE_STUDENT,
            code="STUDENT",
            name="Student",
            loan_rule_set_id=RULE_STUDENT,
        )
    )
    track(
        _add_if_missing(
            session,
            PatronTypeModel,
            TYPE_TEACHER,
            code="TEACHER",
            name="Teacher",
            loan_rule_set_id=RULE_TEACHER,
        )
    )

    for sec_id, grade, section in (
        (SEC_7A, "7", "A"),
        (SEC_8B, "8", "B"),
        (SEC_9C, "9", "C"),
    ):
        track(
            _add_if_missing(
                session,
                ClassSectionModel,
                sec_id,
                grade=grade,
                section=section,
                academic_year="2025-26",
            )
        )

    patrons = [
        (
            PAT_ARJUN,
            "ADM-2025-7001",
            "Arjun Mehta",
            TYPE_STUDENT,
            SEC_7A,
            PatronStatus.ACTIVE,
            "LIB-7001",
        ),
        (
            PAT_PRIYA,
            "ADM-2025-7002",
            "Priya Sharma",
            TYPE_STUDENT,
            SEC_7A,
            PatronStatus.ACTIVE,
            "LIB-7002",
        ),
        (
            PAT_ROHAN,
            "ADM-2025-8001",
            "Rohan Das",
            TYPE_STUDENT,
            SEC_8B,
            PatronStatus.ACTIVE,
            "LIB-8001",
        ),
        (
            PAT_KAVITA,
            "STF-2025-0101",
            "Ms. Kavita Nair",
            TYPE_TEACHER,
            None,
            PatronStatus.ACTIVE,
            "LIB-T101",
        ),
        (
            PAT_SNEHA,
            "ADM-2025-9001",
            "Sneha Patel",
            TYPE_STUDENT,
            SEC_9C,
            PatronStatus.SUSPENDED,
            "LIB-9001",
        ),
    ]
    for pid, ext, name, ptype, sec, status, card in patrons:
        track(
            _add_if_missing(
                session,
                PatronModel,
                pid,
                external_ref=ext,
                display_name=name,
                patron_type_id=ptype,
                class_section_id=sec,
                status=status,
                blocked=False,
                card_barcode=card,
            )
        )

    catalogs = [
        (
            CAT_MATH,
            "NCERT Mathematics Class 7",
            None,
            "9788174507175",
            "en",
            ["mathematics", "textbook", "cbse"],
            "510 NCE",
            "510",
            CatalogingStatus.PUBLISHED,
            "Class set — multiple copies",
        ),
        (
            CAT_PAN,
            "Panchatantra",
            "Selected Stories",
            "9780143335980",
            "hi",
            ["fiction", "folktales", "children"],
            "398 PAN",
            "398.2",
            CatalogingStatus.PUBLISHED,
            None,
        ),
        (
            CAT_NEHRU,
            "Discovery of India",
            None,
            "9780143031031",
            "en",
            ["history", "india", "non-fiction"],
            "954 NEH",
            "954",
            CatalogingStatus.PUBLISHED,
            "Reference copy — staff desk only",
        ),
        (
            CAT_DRAFT,
            "Draft: New Science Textbook",
            None,
            None,
            "en",
            [],
            None,
            None,
            CatalogingStatus.DRAFT,
            "Awaiting cataloguing",
        ),
    ]
    for cid, title, sub, isbn, lang, tags, call, ddc, status, notes in catalogs:
        track(
            _add_if_missing(
                session,
                CatalogModel,
                cid,
                title=title,
                subtitle=sub,
                isbn=isbn,
                language=lang,
                subject_tags=tags,
                call_number=call,
                ddc=ddc,
                cataloging_status=status,
                notes=notes,
            )
        )

    holdings = [
        (
            HLD_MATH1,
            CAT_MATH,
            "BC-MATH7-001",
            "ACC-2025-0001",
            "Stack A-01",
            HoldingStatus.ON_LOAN,
            True,
        ),
        (
            HLD_MATH2,
            CAT_MATH,
            "BC-MATH7-002",
            "ACC-2025-0002",
            "Stack A-01",
            HoldingStatus.ON_LOAN,
            True,
        ),
        (
            HLD_MATH3,
            CAT_MATH,
            "BC-MATH7-003",
            "ACC-2025-0003",
            "Stack A-01",
            HoldingStatus.AVAILABLE,
            True,
        ),
        (
            HLD_PAN1,
            CAT_PAN,
            "BC-PAN-001",
            "ACC-2025-0101",
            "Stack B-12",
            HoldingStatus.AVAILABLE,
            True,
        ),
        (
            HLD_NEHRU,
            CAT_NEHRU,
            "BC-NEH-001",
            "ACC-2025-0201",
            "Reference Desk",
            HoldingStatus.AVAILABLE,
            False,
        ),
        (
            HLD_PAN2,
            CAT_PAN,
            "BC-PAN-002",
            "ACC-2024-0099",
            "Stack B-12",
            HoldingStatus.WITHDRAWN,
            True,
        ),
    ]
    for hid, cat, bc, acc, shelf, status, circ in holdings:
        track(
            _add_if_missing(
                session,
                HoldingModel,
                hid,
                catalog_id=cat,
                barcode=bc,
                accession_number=acc,
                shelf_location=shelf,
                holding_status=status,
                circulating=circ,
            )
        )

    session.flush()

    loans = [
        (
            LOAN_OPEN,
            PAT_ARJUN,
            HLD_MATH1,
            RULE_STUDENT,
            datetime(2026, 5, 20, 5, 0, tzinfo=UTC),
            date(2026, 6, 3),
            None,
        ),
        (
            LOAN_CLOSED,
            PAT_PRIYA,
            HLD_PAN1,
            RULE_STUDENT,
            datetime(2026, 4, 1, 8, 30, tzinfo=UTC),
            date(2026, 4, 15),
            datetime(2026, 4, 14, 11, 15, tzinfo=UTC),
        ),
        (
            LOAN_OVERDUE,
            PAT_ROHAN,
            HLD_MATH2,
            RULE_STUDENT,
            datetime(2026, 4, 10, 3, 30, tzinfo=UTC),
            date(2026, 4, 24),
            None,
        ),
    ]
    for lid, patron, holding, rules, checkout, due, returned in loans:
        track(
            _add_if_missing(
                session,
                LoanModel,
                lid,
                patron_id=patron,
                holding_id=holding,
                loan_rule_set_id=rules,
                checkout_at=checkout,
                due_date=due,
                returned_at=returned,
                checkout_operator_id="dev-librarian",
            )
        )

    session.commit()
    return stats


def main() -> int:
    settings = get_settings()
    print(f"Seeding sample data → {settings.database_url.split('@')[-1]}")
    session = SessionLocal()
    try:
        ensure_default_api_users(session)
        session.commit()
        stats = seed(session)
        print(f"Done. inserted={stats['inserted']} skipped={stats['skipped']}")
        print("\nAPI users (JWT login at POST /api/v1/auth/token):")
        print(f"  admin / {DEFAULT_DEV_PASSWORD}     (ADMIN)")
        print(f"  librarian / {DEFAULT_DEV_PASSWORD} (LIBRARIAN)")
        print(f"  patron / {DEFAULT_DEV_PASSWORD}    (PATRON — read-only scope when enabled)")
        print("\nDesk lookup hints:")
        print("  Patron card LIB-7001 → Arjun Mehta (open loan on BC-MATH7-001)")
        print("  Patron card LIB-8001 → Rohan Das (overdue loan on BC-MATH7-002)")
        print("  Holding BC-PAN-001   → Panchatantra (available)")
        print("  Holding BC-NEH-001   → Discovery of India (reference, non-circulating)")
        return 0
    except Exception as exc:
        session.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
