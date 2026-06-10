-- LMS MVP — sample seed data (K-12 demo library)
-- Run after 001_domain_ddl.sql or `make migrate`.
-- Idempotent: uses fixed UUIDs and ON CONFLICT DO NOTHING.

BEGIN;

-- Loan rule sets
INSERT INTO loan_rule_sets (id, name, max_active_loans, loan_period_days, calendar_policy)
VALUES
    ('00000001-0001-4001-8001-000000000001', 'Student standard', 5, 14, 'CALENDAR_DAYS'),
    ('00000001-0001-4001-8001-000000000002', 'Teacher standard', 10, 30, 'CALENDAR_DAYS')
ON CONFLICT (id) DO NOTHING;

-- Patron types
INSERT INTO patron_types (id, code, name, loan_rule_set_id)
VALUES
    ('00000002-0001-4001-8001-000000000001', 'STUDENT', 'Student', '00000001-0001-4001-8001-000000000001'),
    ('00000002-0001-4001-8001-000000000002', 'TEACHER', 'Teacher', '00000001-0001-4001-8001-000000000002')
ON CONFLICT (id) DO NOTHING;

-- Class sections (2025-26)
INSERT INTO class_sections (id, grade, section, academic_year)
VALUES
    ('00000003-0001-4001-8001-000000000001', '7', 'A', '2025-26'),
    ('00000003-0001-4001-8001-000000000002', '8', 'B', '2025-26'),
    ('00000003-0001-4001-8001-000000000003', '9', 'C', '2025-26')
ON CONFLICT (id) DO NOTHING;

-- Patrons
INSERT INTO patrons (
    id, external_ref, display_name, patron_type_id, class_section_id,
    status, blocked, card_barcode
)
VALUES
    (
        '00000004-0001-4001-8001-000000000001',
        'ADM-2025-7001', 'Arjun Mehta', '00000002-0001-4001-8001-000000000001',
        '00000003-0001-4001-8001-000000000001', 'ACTIVE', false, 'LIB-7001'
    ),
    (
        '00000004-0001-4001-8001-000000000002',
        'ADM-2025-7002', 'Priya Sharma', '00000002-0001-4001-8001-000000000001',
        '00000003-0001-4001-8001-000000000001', 'ACTIVE', false, 'LIB-7002'
    ),
    (
        '00000004-0001-4001-8001-000000000003',
        'ADM-2025-8001', 'Rohan Das', '00000002-0001-4001-8001-000000000001',
        '00000003-0001-4001-8001-000000000002', 'ACTIVE', false, 'LIB-8001'
    ),
    (
        '00000004-0001-4001-8001-000000000004',
        'STF-2025-0101', 'Ms. Kavita Nair', '00000002-0001-4001-8001-000000000002',
        NULL, 'ACTIVE', false, 'LIB-T101'
    ),
    (
        '00000004-0001-4001-8001-000000000005',
        'ADM-2025-9001', 'Sneha Patel', '00000002-0001-4001-8001-000000000001',
        '00000003-0001-4001-8001-000000000003', 'SUSPENDED', false, 'LIB-9001'
    )
ON CONFLICT (id) DO NOTHING;

-- Catalog records (published)
INSERT INTO catalogs (
    id, title, subtitle, isbn, language, subject_tags,
    call_number, ddc, cataloging_status, notes
)
VALUES
    (
        '00000005-0001-4001-8001-000000000001',
        'NCERT Mathematics Class 7',
        NULL, '9788174507175', 'en',
        '["mathematics", "textbook", "cbse"]'::jsonb,
        '510 NCE', '510', 'PUBLISHED', 'Class set — multiple copies'
    ),
    (
        '00000005-0001-4001-8001-000000000002',
        'Panchatantra',
        'Selected Stories',
        '9780143335980', 'hi',
        '["fiction", "folktales", "children"]'::jsonb,
        '398 PAN', '398.2', 'PUBLISHED', NULL
    ),
    (
        '00000005-0001-4001-8001-000000000003',
        'Discovery of India',
        NULL, '9780143031031', 'en',
        '["history", "india", "non-fiction"]'::jsonb,
        '954 NEH', '954', 'PUBLISHED', 'Reference copy — staff desk only'
    ),
    (
        '00000005-0001-4001-8001-000000000004',
        'Draft: New Science Textbook',
        NULL, NULL, 'en', '[]'::jsonb,
        NULL, NULL, 'DRAFT', 'Awaiting cataloguing'
    )
ON CONFLICT (id) DO NOTHING;

-- Holdings
INSERT INTO holdings (
    id, catalog_id, barcode, accession_number, shelf_location,
    holding_status, circulating
)
VALUES
    -- Math textbooks (2 available, 1 on loan)
    (
        '00000006-0001-4001-8001-000000000001',
        '00000005-0001-4001-8001-000000000001',
        'BC-MATH7-001', 'ACC-2025-0001', 'Stack A-01', 'ON_LOAN', true
    ),
    (
        '00000006-0001-4001-8001-000000000002',
        '00000005-0001-4001-8001-000000000001',
        'BC-MATH7-002', 'ACC-2025-0002', 'Stack A-01', 'AVAILABLE', true
    ),
    (
        '00000006-0001-4001-8001-000000000003',
        '00000005-0001-4001-8001-000000000001',
        'BC-MATH7-003', 'ACC-2025-0003', 'Stack A-01', 'AVAILABLE', true
    ),
    -- Panchatantra
    (
        '00000006-0001-4001-8001-000000000004',
        '00000005-0001-4001-8001-000000000002',
        'BC-PAN-001', 'ACC-2025-0101', 'Stack B-12', 'AVAILABLE', true
    ),
    -- Discovery of India (reference only)
    (
        '00000006-0001-4001-8001-000000000005',
        '00000005-0001-4001-8001-000000000003',
        'BC-NEH-001', 'ACC-2025-0201', 'Reference Desk', 'AVAILABLE', false
    ),
    -- Withdrawn copy
    (
        '00000006-0001-4001-8001-000000000006',
        '00000005-0001-4001-8001-000000000002',
        'BC-PAN-002', 'ACC-2024-0099', 'Stack B-12', 'WITHDRAWN', true
    )
ON CONFLICT (id) DO NOTHING;

-- Loans: one open (Arjun → Math copy 1), one closed, one overdue
INSERT INTO loans (
    id, patron_id, holding_id, loan_rule_set_id,
    checkout_at, due_date, returned_at, checkout_operator_id
)
VALUES
    (
        '00000007-0001-4001-8001-000000000001',
        '00000004-0001-4001-8001-000000000001',
        '00000006-0001-4001-8001-000000000001',
        '00000001-0001-4001-8001-000000000001',
        timestamptz '2026-05-20 10:30:00+05:30',
        DATE '2026-06-03',
        NULL,
        'dev-librarian'
    ),
    (
        '00000007-0001-4001-8001-000000000002',
        '00000004-0001-4001-8001-000000000002',
        '00000006-0001-4001-8001-000000000004',
        '00000001-0001-4001-8001-000000000001',
        timestamptz '2026-04-01 14:00:00+05:30',
        DATE '2026-04-15',
        timestamptz '2026-04-14 16:45:00+05:30',
        'dev-librarian'
    ),
    (
        '00000007-0001-4001-8001-000000000003',
        '00000004-0001-4001-8001-000000000003',
        '00000006-0001-4001-8001-000000000002',
        '00000001-0001-4001-8001-000000000001',
        timestamptz '2026-04-10 09:00:00+05:30',
        DATE '2026-04-24',
        NULL,
        'dev-librarian'
    )
ON CONFLICT (id) DO NOTHING;

-- Mark overdue holding as ON_LOAN (Rohan still has Math copy 2)
UPDATE holdings
SET holding_status = 'ON_LOAN', updated_at = now()
WHERE id = '00000006-0001-4001-8001-000000000002'
  AND holding_status <> 'ON_LOAN';

COMMIT;

-- Quick verification (optional)
-- SELECT pt.code, p.display_name, p.card_barcode FROM patrons p JOIN patron_types pt ON pt.id = p.patron_type_id;
-- SELECT c.title, h.barcode, h.holding_status FROM holdings h JOIN catalogs c ON c.id = h.catalog_id;
-- SELECT p.display_name, c.title, l.due_date, l.returned_at FROM loans l
--   JOIN patrons p ON p.id = l.patron_id JOIN holdings h ON h.id = l.holding_id
--   JOIN catalogs c ON c.id = h.catalog_id;
