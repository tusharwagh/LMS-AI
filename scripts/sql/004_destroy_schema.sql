-- LMS MVP — drop all application schema (domain + idempotency + migration tracking)
-- Order respects foreign keys. Reversible via `make migrate` or 001_domain_ddl.sql.

BEGIN;

DROP INDEX IF EXISTS ix_circulation_fulfillments_loan_id;
DROP INDEX IF EXISTS ix_loans_due_date_open;
DROP INDEX IF EXISTS ix_loans_patron_open;
DROP INDEX IF EXISTS ix_holdings_catalog_id;
DROP INDEX IF EXISTS ix_patrons_card_barcode;
DROP INDEX IF EXISTS ix_patrons_external_ref;
DROP INDEX IF EXISTS uq_loan_open_holding;

DROP TABLE IF EXISTS circulation_fulfillments CASCADE;
DROP TABLE IF EXISTS loans CASCADE;
DROP TABLE IF EXISTS holdings CASCADE;
DROP TABLE IF EXISTS catalogs CASCADE;
DROP TABLE IF EXISTS patron_blocks CASCADE;
DROP TABLE IF EXISTS patrons CASCADE;
DROP TABLE IF EXISTS class_sections CASCADE;
DROP TABLE IF EXISTS patron_types CASCADE;
DROP TABLE IF EXISTS loan_rule_sets CASCADE;
DROP TABLE IF EXISTS idempotency_records CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;

COMMIT;
