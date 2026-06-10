-- LMS MVP — full PostgreSQL DDL (Reference, Catalog, Loan + shared idempotency)
-- Generated from Alembic revisions 001 + 002. Prefer `make migrate` for live databases.

BEGIN;

-- ---------------------------------------------------------------------------
-- Shared: idempotency store (circulation checkout/return)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS idempotency_records (
    id              SERIAL PRIMARY KEY,
    scope_key       VARCHAR(512) NOT NULL,
    idempotency_key VARCHAR(64)  NOT NULL,
    payload_hash    VARCHAR(64)  NOT NULL,
    response_status INTEGER      NOT NULL,
    response_body   TEXT         NOT NULL,
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_idempotency_scope_key UNIQUE (scope_key, idempotency_key)
);

-- ---------------------------------------------------------------------------
-- Loan: circulation policy
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loan_rule_sets (
    id               UUID         PRIMARY KEY,
    name             VARCHAR(128) NOT NULL,
    max_active_loans INTEGER      NOT NULL,
    loan_period_days INTEGER      NOT NULL,
    calendar_policy  VARCHAR(32)  NOT NULL DEFAULT 'CALENDAR_DAYS',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Reference: patron classification & cohorts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patron_types (
    id               UUID         PRIMARY KEY,
    code             VARCHAR(64)  NOT NULL UNIQUE,
    name             VARCHAR(255) NOT NULL,
    loan_rule_set_id UUID         REFERENCES loan_rule_sets (id),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS class_sections (
    id            UUID        PRIMARY KEY,
    grade         VARCHAR(32) NOT NULL,
    section       VARCHAR(32) NOT NULL,
    academic_year VARCHAR(16) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_class_section UNIQUE (grade, section, academic_year)
);

CREATE TABLE IF NOT EXISTS patrons (
    id               UUID         PRIMARY KEY,
    external_ref     VARCHAR(128) UNIQUE,
    display_name     VARCHAR(255) NOT NULL,
    patron_type_id   UUID         NOT NULL REFERENCES patron_types (id),
    class_section_id UUID         REFERENCES class_sections (id),
    status           VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
    blocked          BOOLEAN      NOT NULL DEFAULT false,
    card_barcode     VARCHAR(64)  UNIQUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS patron_blocks (
    id          UUID        PRIMARY KEY,
    patron_id   UUID        NOT NULL REFERENCES patrons (id),
    reason_code VARCHAR(64) NOT NULL,
    active      BOOLEAN     NOT NULL DEFAULT true,
    start_at    TIMESTAMPTZ NOT NULL,
    end_at      TIMESTAMPTZ,
    notes       TEXT
);

-- ---------------------------------------------------------------------------
-- Catalog: bibliographic records & physical holdings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS catalogs (
    id                UUID         PRIMARY KEY,
    title             VARCHAR(512) NOT NULL,
    subtitle          VARCHAR(512),
    isbn              VARCHAR(20),
    language          VARCHAR(16)  NOT NULL DEFAULT 'en',
    subject_tags      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    call_number       VARCHAR(64),
    ddc               VARCHAR(32),
    cataloging_status VARCHAR(32)  NOT NULL DEFAULT 'DRAFT',
    notes             TEXT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS holdings (
    id               UUID         PRIMARY KEY,
    catalog_id       UUID         NOT NULL REFERENCES catalogs (id),
    barcode          VARCHAR(64)  NOT NULL UNIQUE,
    accession_number VARCHAR(64)  NOT NULL UNIQUE,
    shelf_location   VARCHAR(128),
    holding_status   VARCHAR(32)  NOT NULL DEFAULT 'AVAILABLE',
    circulating      BOOLEAN      NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Loan: circulation transactions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loans (
    id                   UUID        PRIMARY KEY,
    patron_id            UUID        NOT NULL REFERENCES patrons (id),
    holding_id           UUID        NOT NULL REFERENCES holdings (id),
    loan_rule_set_id     UUID        REFERENCES loan_rule_sets (id),
    checkout_at          TIMESTAMPTZ NOT NULL,
    due_date             DATE        NOT NULL,
    returned_at          TIMESTAMPTZ,
    checkout_operator_id VARCHAR(128),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- At most one open loan per holding (MVP invariant REQ-24)
CREATE UNIQUE INDEX IF NOT EXISTS uq_loan_open_holding
    ON loans (holding_id)
    WHERE returned_at IS NULL;

-- Helpful lookup indexes (not in Alembic; safe for dev/reporting)
CREATE INDEX IF NOT EXISTS ix_patrons_external_ref ON patrons (external_ref);
CREATE INDEX IF NOT EXISTS ix_patrons_card_barcode ON patrons (card_barcode);
CREATE INDEX IF NOT EXISTS ix_holdings_catalog_id ON holdings (catalog_id);
CREATE INDEX IF NOT EXISTS ix_loans_patron_open ON loans (patron_id) WHERE returned_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_loans_due_date_open ON loans (due_date) WHERE returned_at IS NULL;

COMMIT;
