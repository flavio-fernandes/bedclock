import pytest

from bedclock import systemstats


def test_uptime_parsing_converts_seconds_to_whole_minutes():
    assert systemstats.parse_uptime_minutes("125.99 456.00\n") == 2


def test_uptime_parsing_accepts_normal_two_field_linux_format():
    assert systemstats.parse_uptime_minutes("3600.50 12345.67\n") == 60


@pytest.mark.parametrize("text", ["", "not-a-number 0", "-1.0 0"])
def test_invalid_uptime_data_is_rejected(text):
    with pytest.raises(ValueError):
        systemstats.parse_uptime_minutes(text)


def test_mem_available_selected_from_realistic_meminfo():
    text = """MemTotal:         500000 kB
MemFree:          123456 kB
Buffers:            1000 kB
MemAvailable:     234567 kB
Cached:            20000 kB
"""
    assert systemstats.parse_mem_available_kb(text) == 234567


def test_mem_available_value_is_returned_unchanged_in_kb():
    assert systemstats.parse_mem_available_kb("MemAvailable:       17 kB\n") == 17


@pytest.mark.parametrize(
    "text",
    [
        "MemTotal: 100 kB\nMemFree: 99 kB\n",
        "MemAvailable:\n",
        "MemAvailable: nope kB\n",
        "MemAvailable: -1 kB\n",
    ],
)
def test_missing_or_malformed_mem_available_is_rejected(text):
    with pytest.raises(ValueError):
        systemstats.parse_mem_available_kb(text)


def test_read_helpers_accept_injected_reader():
    def reader(path):
        assert path == "/fake"
        return "60.00 0.00\n"

    assert systemstats.read_uptime_minutes("/fake", reader=reader) == 1
