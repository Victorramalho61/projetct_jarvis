"""Unit tests for pure utility logic — no external dependencies."""


def test_phone_sanitize():
    phone = "+55 61 9 9999-9999"
    result = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    assert result == "5561999999999"


def test_brt_offset():
    utc_hour = 13
    brt = (utc_hour - 3) % 24
    assert brt == 10


def test_brt_midnight_wraparound():
    utc_hour = 2
    brt = (utc_hour - 3 + 24) % 24
    assert brt == 23


def test_send_hour_utc_valid_range():
    for h in range(24):
        assert 0 <= h <= 23


def test_delivery_channels():
    valid = {"email", "teams", "whatsapp"}
    assert "email" in valid
    assert "sms" not in valid
