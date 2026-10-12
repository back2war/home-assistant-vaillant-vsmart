"""Parsing of boiler error codes reported by the /api/homestatus endpoint.

The official Vaillant vSMART app reads the list ``boiler_error`` from the
modules returned by ``api/homestatus`` and shows dashboard warnings for it,
e.g. ``water_pressure`` -> "Water pressure low, please refill".
"""
from __future__ import annotations

from typing import Any

HOMESTATUS_PATH = "api/homestatus"

WATER_PRESSURE = "water_pressure"
MAINTENANCE = "maintenance"
BOILER_ERROR_INTERNAL = "boiler_error_internal"

KNOWN_BOILER_ERRORS = (
    "boiler_responding",
    "boiler_not_responding",
    MAINTENANCE,
    WATER_PRESSURE,
    "boiler_flame",
    "air_pressure",
    "boiler_temperature",
    BOILER_ERROR_INTERNAL,
)


def parse_boiler_errors(body: dict[str, Any]) -> dict[str, list[str]]:
    """Return boiler errors per module id from a homestatus response."""

    modules = (body.get("body") or {}).get("home", {}).get("modules") or []
    result: dict[str, list[str]] = {}
    for module in modules:
        module_id = module.get("id")
        if not module_id or "boiler_error" not in module:
            continue
        errors = module.get("boiler_error") or []
        if isinstance(errors, str):
            errors = [errors]
        result[module_id] = sorted({str(e) for e in errors if e})
    return result


def errors_for_device(errors_by_module: dict[str, list[str]], device_id: str) -> list[str]:
    """Return the boiler errors relevant for a device.

    The gateway module usually has the same id as the device of the old API.
    If it cannot be matched, all errors of the home are returned.
    """

    if device_id in errors_by_module:
        return errors_by_module[device_id]
    return sorted({e for errors in errors_by_module.values() for e in errors})
