import pytest

from nour_transfers.rules import can_transfer, days_of_cover, priority


def test_cover_is_stock_over_sales():
    assert days_of_cover(40, 8) == 5.0
    assert isinstance(days_of_cover(9, 2), float)


def test_no_sales_lasts_indefinitely():
    assert days_of_cover(12, 0) is None
    assert days_of_cover(0, 0) is None
    assert priority(True, None) == "normal"


def test_negative_inputs_raise():
    with pytest.raises(ValueError):
        days_of_cover(-1, 2)
    with pytest.raises(ValueError):
        days_of_cover(1, -2)
    with pytest.raises(ValueError):
        days_of_cover(-1, -2)


def test_priority_boundaries():
    assert priority(True, 2.99) == "urgent"
    assert priority(True, 3.0) == "high"        # exactly three days is not urgent
    assert priority(False, 2.0) == "high"       # only chronic items are urgent
    assert priority(True, 6.99) == "high"
    assert priority(True, 7.0) == "normal"
    assert priority(False, 100.0) == "normal"


def test_can_transfer_keeps_exactly_the_reserve():
    assert can_transfer(40, 30, 10) is True
    assert can_transfer(40, 31, 10) is False
    assert can_transfer(10, 5, 5) is True       # leaves exactly the reserve
    assert can_transfer(10, 6, 5) is False


def test_can_transfer_needs_a_positive_quantity():
    assert can_transfer(100, 0, 0) is False
    assert can_transfer(100, -1, 0) is False
    assert can_transfer(100, 1, 0) is True
    assert can_transfer(0, 1, 0) is False
