from enum import StrEnum


class CalendarPolicy(StrEnum):
    CALENDAR_DAYS = "CALENDAR_DAYS"


class FulfillmentDirection(StrEnum):
    ISSUE = "ISSUE"
    RETURN = "RETURN"


class FulfillmentMode(StrEnum):
    DESK = "DESK"
    DELIVERY = "DELIVERY"
    PICKUP_POINT = "PICKUP_POINT"


class FulfillmentStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUESTED = "REQUESTED"
    READY = "READY"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
