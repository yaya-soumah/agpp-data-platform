from enum import StrEnum

class OrderStatus(StrEnum):
    """Supported lifecycle states for a customer order."""

    PLACED = "PLACED"
    CANCELLED = "CANCELLED"

ORDER_STATUS_VALUES = tuple(status.value for status in OrderStatus)
