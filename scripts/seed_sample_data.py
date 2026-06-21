#!/usr/bin/env python3
"""Load MVP sample data into PostgreSQL (idempotent).

Uses fixed seed UUIDs from scripts/sql/002_sample_data.sql plus bulk K-12 rows
(~1,600 domain records by default). Safe to re-run: clears the seed UUID namespace first.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
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

# Bulk seed sizing — override with SEED_MIN_RECORDS (target domain rows, excluding API users)
DEFAULT_SEED_MIN_RECORDS = 1500
BULK_PATRON_COUNT = 400
BULK_CATALOG_COUNT = 200
BULK_HOLDINGS_PER_CATALOG = 3
BULK_LOAN_COUNT = 350

_FIRST_NAMES = (
    "Aarav",
    "Ananya",
    "Vihaan",
    "Isha",
    "Kabir",
    "Meera",
    "Rohan",
    "Sneha",
    "Arjun",
    "Priya",
    "Dev",
    "Kavya",
    "Aditya",
    "Nisha",
    "Rahul",
    "Pooja",
)
_LAST_NAMES = (
    "Sharma",
    "Patel",
    "Mehta",
    "Das",
    "Nair",
    "Gupta",
    "Reddy",
    "Iyer",
    "Khan",
    "Singh",
    "Verma",
    "Joshi",
)
_SUBJECTS = (
    "Mathematics",
    "Science",
    "English",
    "Hindi",
    "Social Studies",
    "Physics",
    "Chemistry",
    "Biology",
    "History",
    "Geography",
    "Computer Science",
    "Economics",
)
_DDC_PREFIXES = ("510", "500", "820", "891", "300", "530", "540", "570", "900", "910", "004", "330")


def _seed_uuid(entity_prefix: int, seq: int) -> uuid.UUID:
    return uuid.UUID(f"0000000{entity_prefix}-0001-4001-8001-{seq:012d}")


def _bulk_target() -> int:
    raw = os.environ.get("SEED_MIN_RECORDS", str(DEFAULT_SEED_MIN_RECORDS))
    try:
        return max(100, int(raw))
    except ValueError:
        return DEFAULT_SEED_MIN_RECORDS


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


def _seed_bulk_class_sections(session, track) -> dict[tuple[str, str], uuid.UUID]:
    """Extra grades 6–12 × sections A–F (demo 7A/8B/9C already seeded)."""
    section_ids: dict[tuple[str, str], uuid.UUID] = {
        ("7", "A"): SEC_7A,
        ("8", "B"): SEC_8B,
        ("9", "C"): SEC_9C,
    }
    seq = 4
    for grade in ("6", "7", "8", "9", "10", "11", "12"):
        for section in ("A", "B", "C", "D", "E", "F"):
            key = (grade, section)
            if key in section_ids:
                continue
            sec_id = _seed_uuid(3, seq)
            section_ids[key] = sec_id
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
            seq += 1
    return section_ids


def _seed_bulk_patrons(session, track, section_ids: dict[tuple[str, str], uuid.UUID]) -> list[uuid.UUID]:
    patron_ids: list[uuid.UUID] = []
    section_keys = sorted(section_ids.keys())
    for index in range(BULK_PATRON_COUNT):
        seq = index + 6
        patron_id = _seed_uuid(4, seq)
        grade, section = section_keys[index % len(section_keys)]
        first = _FIRST_NAMES[index % len(_FIRST_NAMES)]
        last = _LAST_NAMES[(index // len(_FIRST_NAMES)) % len(_LAST_NAMES)]
        track(
            _add_if_missing(
                session,
                PatronModel,
                patron_id,
                external_ref=f"ADM-2025-{grade}{section}{index + 1:04d}",
                display_name=f"{first} {last}",
                patron_type_id=TYPE_STUDENT,
                class_section_id=section_ids[(grade, section)],
                status=PatronStatus.SUSPENDED if index % 47 == 0 else PatronStatus.ACTIVE,
                blocked=False,
                card_barcode=f"LIB-{grade}{section}{index + 1:04d}",
            )
        )
        patron_ids.append(patron_id)
    return patron_ids


def _seed_bulk_catalogs(session, track) -> list[uuid.UUID]:
    catalog_ids: list[uuid.UUID] = []
    for index in range(BULK_CATALOG_COUNT):
        seq = index + 5
        catalog_id = _seed_uuid(5, seq)
        subject = _SUBJECTS[index % len(_SUBJECTS)]
        grade = 6 + (index % 7)
        ddc = _DDC_PREFIXES[index % len(_DDC_PREFIXES)]
        track(
            _add_if_missing(
                session,
                CatalogModel,
                catalog_id,
                title=f"NCERT {subject} Class {grade}",
                subtitle=f"Volume {(index % 3) + 1}" if index % 4 == 0 else None,
                isbn=f"978817450{7000 + index:04d}" if index % 5 else None,
                language="hi" if subject == "Hindi" else "en",
                subject_tags=[subject.lower().replace(" ", "-"), "textbook", "cbse"],
                call_number=f"{ddc} NC{index:03d}",
                ddc=ddc,
                cataloging_status=(
                    CatalogingStatus.DRAFT if index % 29 == 0 else CatalogingStatus.PUBLISHED
                ),
                notes="Bulk seed title" if index % 17 == 0 else None,
            )
        )
        catalog_ids.append(catalog_id)
    return catalog_ids


def _seed_bulk_holdings(
    session,
    track,
    catalog_ids: list[uuid.UUID],
) -> list[tuple[uuid.UUID, uuid.UUID, str]]:
    """Return (holding_id, catalog_id, status) for loan assignment."""
    holdings: list[tuple[uuid.UUID, uuid.UUID, str]] = []
    seq = 7
    stacks = ("Stack A-01", "Stack A-02", "Stack B-10", "Stack B-12", "Stack C-04", "Reference")
    for cat_index, catalog_id in enumerate(catalog_ids):
        for copy in range(BULK_HOLDINGS_PER_CATALOG):
            holding_id = _seed_uuid(6, seq)
            if seq % 701 == 0:
                status = HoldingStatus.LOST
            elif seq % 503 == 0:
                status = HoldingStatus.DAMAGED
            elif seq % 61 == 0:
                status = HoldingStatus.WITHDRAWN
            else:
                status = HoldingStatus.AVAILABLE
            circulating = seq % 41 != 0 and status == HoldingStatus.AVAILABLE
            track(
                _add_if_missing(
                    session,
                    HoldingModel,
                    holding_id,
                    catalog_id=catalog_id,
                    barcode=f"BC-SEED-{seq:05d}",
                    accession_number=f"ACC-2025-{seq:06d}",
                    shelf_location=stacks[(cat_index + copy) % len(stacks)],
                    holding_status=status,
                    circulating=circulating,
                )
            )
            if status == HoldingStatus.AVAILABLE and circulating:
                holdings.append((holding_id, catalog_id, status))
            seq += 1
    return holdings


def _seed_bulk_loans(
    session,
    track,
    patron_ids: list[uuid.UUID],
    lendable_holdings: list[tuple[uuid.UUID, uuid.UUID, str]],
) -> None:
    now = datetime.now(UTC)
    loan_count = min(BULK_LOAN_COUNT, len(patron_ids), len(lendable_holdings))
    for index in range(loan_count):
        loan_id = _seed_uuid(7, index + 4)
        patron_id = patron_ids[index]
        holding_id, _, _ = lendable_holdings[index]
        phase = index % 10
        if phase < 4:
            checkout = now - timedelta(days=20 + index)
            due = (checkout + timedelta(days=14)).date()
            returned = checkout + timedelta(days=10)
            holding_status = HoldingStatus.AVAILABLE
        elif phase < 7:
            checkout = now - timedelta(days=5 + (index % 3))
            due = (now + timedelta(days=7 + (index % 5))).date()
            returned = None
            holding_status = HoldingStatus.ON_LOAN
        else:
            checkout = now - timedelta(days=30 + (index % 10))
            due = (now - timedelta(days=5 + (index % 7))).date()
            returned = None
            holding_status = HoldingStatus.ON_LOAN

        track(
            _add_if_missing(
                session,
                LoanModel,
                loan_id,
                patron_id=patron_id,
                holding_id=holding_id,
                loan_rule_set_id=RULE_STUDENT,
                checkout_at=checkout,
                due_date=due,
                returned_at=returned,
                checkout_operator_id="dev-librarian",
            )
        )
        holding = session.get(HoldingModel, holding_id)
        if holding is not None and returned is None:
            holding.holding_status = holding_status


def _seed_bulk(session, track) -> None:
    section_ids = _seed_bulk_class_sections(session, track)
    patron_ids = _seed_bulk_patrons(session, track, section_ids)
    catalog_ids = _seed_bulk_catalogs(session, track)
    lendable = _seed_bulk_holdings(session, track, catalog_ids)
    session.flush()
    _seed_bulk_loans(session, track, patron_ids, lendable)


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

    _seed_bulk(session, track)

    session.commit()
    stats["total_records"] = stats["inserted"]
    return stats


def main() -> int:
    settings = get_settings()
    print(f"Seeding sample data → {settings.database_url.split('@')[-1]}")
    session = SessionLocal()
    try:
        ensure_default_api_users(session)
        session.commit()
        stats = seed(session)
        target = _bulk_target()
        print(
            f"Done. inserted={stats['inserted']} skipped={stats['skipped']} "
            f"(target ≥{target} domain rows)"
        )
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
