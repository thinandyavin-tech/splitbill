"""Money parsing and splitting. All arithmetic happens in integer satang."""

import re
from decimal import Decimal

from app.errors import ValidationFailed

# NUMERIC(12,2) holds at most 10 digits before the decimal point.
MAX_SATANG = 10**12 - 1
_AMOUNT_RE = re.compile(r"^\d{1,10}(\.\d{1,2})?$")


def parse_satang(value: str, field: str, allow_zero: bool = False) -> int:
    """Parse a string like "1000.00" into satang, rejecting floats and over-precise values."""
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a string such as \"100.00\"")
    if not _AMOUNT_RE.match(value):
        if re.match(r"^\d+\.\d{3,}$", value):
            raise ValidationFailed(f"{field} must have at most 2 decimal places")
        raise ValidationFailed(f"{field} must be a positive amount such as \"100.00\"")
    satang = int(Decimal(value) * 100)
    if satang == 0 and not allow_zero:
        raise ValidationFailed(f"{field} must be greater than 0.00")
    if satang > MAX_SATANG:
        raise ValidationFailed(f"{field} is too large")
    return satang


def to_decimal(satang: int) -> Decimal:
    return Decimal(satang).scaleb(-2).quantize(Decimal("0.01"))


def format_amount(satang: int) -> str:
    return str(to_decimal(satang))


def split_equal(total: int, members: list[str]) -> dict[str, int]:
    """Equal shares; leftover satang go one at a time to members in the order listed."""
    base, remainder = divmod(total, len(members))
    return {m: base + (1 if i < remainder else 0) for i, m in enumerate(members)}
