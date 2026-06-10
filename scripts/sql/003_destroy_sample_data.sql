-- LMS MVP — remove sample seed rows only (fixed demo UUID namespace)
-- Safe to run on shared dev DBs; does not drop schema.
-- Seed IDs match scripts/seed_sample_data.py and 002_sample_data.sql

BEGIN;

DELETE FROM idempotency_records
WHERE scope_key LIKE 'checkout:00000006-%'
   OR scope_key LIKE 'return:00000006-%';

DELETE FROM loans
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM patron_blocks
WHERE patron_id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM holdings
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM catalogs
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM patrons
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM class_sections
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM patron_types
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

DELETE FROM loan_rule_sets
WHERE id::text ~ '^0000000[0-9]-0001-4001-8001-';

COMMIT;
