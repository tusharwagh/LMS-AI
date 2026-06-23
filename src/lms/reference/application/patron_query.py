"""Parse staff patron lookup strings — UUID, CARD-*, ADM-*, or partial name wildcards."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

_CARD_BARCODE_RE = re.compile(r"^CARD-[A-Za-z0-9-]+$", re.I)
_EXTERNAL_REF_RE = re.compile(r"^ADM-[A-Za-z0-9-]+$", re.I)


@dataclass(frozen=True, slots=True)
class ParsedPatronQuery:
    patron_id: UUID | None = None
    card_barcode: str | None = None
    external_ref: str | None = None
    display_name: str | None = None


def normalize_patron_query_text(query: str) -> str:
    return query.strip().rstrip("?.!,").strip()


def parse_patron_query(query: str) -> ParsedPatronQuery:
    """Split a lookup string into explicit business keys or a name wildcard term."""
    term = normalize_patron_query_text(query)
    if not term:
        return ParsedPatronQuery()

    try:
        return ParsedPatronQuery(patron_id=UUID(term))
    except ValueError:
        pass

    if _CARD_BARCODE_RE.match(term):
        return ParsedPatronQuery(card_barcode=term)

    if _EXTERNAL_REF_RE.match(term):
        return ParsedPatronQuery(external_ref=term)

    return ParsedPatronQuery(display_name=term)
