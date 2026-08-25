#!/usr/bin/env python3
"""Helpers for reading Linux operational state from /proc."""


def _read_text(path, reader=None):
    if reader is not None:
        return reader(path)
    with open(path, "r") as f:
        return f.read()


def parse_uptime_minutes(text):
    fields = text.split()
    if not fields:
        raise ValueError("missing uptime seconds")
    uptime_seconds = float(fields[0])
    if uptime_seconds < 0:
        raise ValueError("negative uptime seconds")
    return int(uptime_seconds / 60)


def read_uptime_minutes(path="/proc/uptime", reader=None):
    return parse_uptime_minutes(_read_text(path, reader))


def parse_mem_available_kb(text):
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "MemAvailable:":
            if len(parts) < 2:
                raise ValueError("malformed MemAvailable line")
            value = int(parts[1])
            if value < 0:
                raise ValueError("negative MemAvailable")
            return value
    raise ValueError("MemAvailable not found")


def read_mem_available_kb(path="/proc/meminfo", reader=None):
    return parse_mem_available_kb(_read_text(path, reader))
