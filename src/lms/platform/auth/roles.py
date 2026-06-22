from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    LIBRARIAN = "LIBRARIAN"
    PATRON = "PATRON"


# MVP D4: librarian-only checkout; PATRON is read-only for circulation writes.
CIRCULATION_WRITE_ROLES = frozenset({Role.ADMIN, Role.LIBRARIAN})
ADMIN_CONFIG_ROLES = frozenset({Role.ADMIN})
STAFF_READ_ROLES = frozenset({Role.ADMIN, Role.LIBRARIAN})
PATRON_READ_ROLES = frozenset({Role.PATRON})
