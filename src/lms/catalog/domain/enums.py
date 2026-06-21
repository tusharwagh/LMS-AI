from enum import StrEnum


class CatalogingStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPPRESSED = "SUPPRESSED"


class HoldingStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ON_LOAN = "ON_LOAN"
    WITHDRAWN = "WITHDRAWN"
    DAMAGED = "DAMAGED"
    LOST = "LOST"
