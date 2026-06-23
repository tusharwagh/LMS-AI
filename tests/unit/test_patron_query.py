"""Unit tests for patron business-key query parsing."""

from __future__ import annotations

from uuid import UUID

import pytest

from lms.reference.application.patron_query import parse_patron_query

pytestmark = pytest.mark.unit


def test_parse_patron_query_uuid() -> None:
    patron_id = UUID("00000000-0001-4001-8001-000000000099")
    parsed = parse_patron_query(str(patron_id))
    assert parsed.patron_id == patron_id
    assert parsed.card_barcode is None


def test_parse_patron_query_card_barcode() -> None:
    parsed = parse_patron_query("card-12345")
    assert parsed.card_barcode == "card-12345"
    assert parsed.display_name is None


def test_parse_patron_query_external_ref() -> None:
    parsed = parse_patron_query("ADM-2024-001")
    assert parsed.external_ref == "ADM-2024-001"


def test_parse_patron_query_partial_name_strips_punctuation() -> None:
    parsed = parse_patron_query("Priya?")
    assert parsed.display_name == "Priya"
    assert parsed.card_barcode is None
