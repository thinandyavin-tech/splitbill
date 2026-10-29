import pytest

from app.errors import ValidationFailed
from app.money import format_amount, parse_satang, split_equal


def test_equal_split_100_three_ways():
    shares = split_equal(10000, ["alice", "bob", "carol"])
    assert [format_amount(s) for s in shares.values()] == ["33.34", "33.33", "33.33"]
    assert sum(shares.values()) == 10000


def test_equal_split_remainder_follows_listed_order():
    shares = split_equal(100002, ["carol", "bob", "alice"])
    assert shares == {"carol": 33334, "bob": 33334, "alice": 33334}
    shares = split_equal(100001, ["carol", "bob", "alice"])
    assert shares == {"carol": 33334, "bob": 33334, "alice": 33333}


@pytest.mark.parametrize("value", ["10.005", "1.999"])
def test_three_decimal_places_rejected(value):
    with pytest.raises(ValidationFailed, match="at most 2 decimal places"):
        parse_satang(value, "amount")


@pytest.mark.parametrize(
    "value",
    ["0", "0.00", "-5.00", "abc", "", "1e3", " 1.00", "1,000.00", "100.00\n", "๑๐๐", ".50", "5."],
)
def test_invalid_or_non_positive_rejected(value):
    with pytest.raises(ValidationFailed):
        parse_satang(value, "amount")


def test_non_string_rejected():
    with pytest.raises(ValidationFailed, match="must be a string"):
        parse_satang(10.5, "amount")  # type: ignore[arg-type]


@pytest.mark.parametrize(("value", "satang"), [("1000.00", 100000), ("0.1", 10), ("7", 700)])
def test_parse(value, satang):
    assert parse_satang(value, "amount") == satang


def test_too_large_rejected():
    with pytest.raises(ValidationFailed):
        parse_satang("10000000000.00", "amount")
    assert parse_satang("9999999999.99", "amount") == 999999999999
