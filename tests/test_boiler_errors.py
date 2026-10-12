"""Tests for boiler error parsing and the binary sensor platform."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from custom_components.vaillant_vsmart.binary_sensor import (
    VaillantBoilerErrorBinarySensor,
    VaillantBoilerProblemBinarySensor,
)
from custom_components.vaillant_vsmart.boiler_errors import (
    MAINTENANCE,
    WATER_PRESSURE,
    errors_for_device,
    parse_boiler_errors,
)
from custom_components.vaillant_vsmart.entity import VaillantCoordinator

HOMESTATUS = {
    "status": "ok",
    "body": {
        "home": {
            "id": "home1",
            "modules": [
                {
                    "id": "70:ee:50:00:00:01",
                    "type": "NAVaillant",
                    "boiler_error": ["water_pressure"],
                },
                {"id": "04:00:00:00:00:02", "type": "NAThermVaillant"},
            ],
        }
    },
}


def test_parse_boiler_errors():
    """Only modules with a boiler_error key are returned."""
    assert parse_boiler_errors(HOMESTATUS) == {"70:ee:50:00:00:01": ["water_pressure"]}


def test_parse_boiler_errors_empty_and_string():
    """Empty bodies and single string values are handled."""
    assert parse_boiler_errors({}) == {}
    body = {"body": {"home": {"modules": [{"id": "a", "boiler_error": "maintenance"}]}}}
    assert parse_boiler_errors(body) == {"a": ["maintenance"]}


def test_errors_for_device_match_and_fallback():
    """Device id is matched directly, otherwise all errors are merged."""
    errors = {"a": ["water_pressure"], "b": ["maintenance"]}
    assert errors_for_device(errors, "a") == ["water_pressure"]
    assert errors_for_device(errors, "x") == ["maintenance", "water_pressure"]


def _sensor(cls, boiler_errors, *args):
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = SimpleNamespace(
        boiler_errors=boiler_errors,
        devices={"dev": SimpleNamespace(id="dev")},
    )
    return cls(coordinator, "dev", *args)


def test_binary_sensors_state():
    """Sensors reflect the error list of the device."""
    errors = {"dev": [WATER_PRESSURE]}
    assert _sensor(VaillantBoilerErrorBinarySensor, errors, WATER_PRESSURE).is_on
    assert not _sensor(VaillantBoilerErrorBinarySensor, errors, MAINTENANCE).is_on
    problem = _sensor(VaillantBoilerProblemBinarySensor, errors)
    assert problem.is_on
    assert problem.extra_state_attributes == {"boiler_errors": [WATER_PRESSURE]}
    assert not _sensor(
        VaillantBoilerProblemBinarySensor, {"dev": ["boiler_responding"]}
    ).is_on


def test_binary_sensor_unavailable_without_homestatus():
    """Sensors are unavailable if homestatus could not be read."""
    assert not _sensor(VaillantBoilerProblemBinarySensor, None).available
    assert _sensor(VaillantBoilerProblemBinarySensor, {}).available


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (HOMESTATUS, {"70:ee:50:00:00:01": ["water_pressure"]}),
        ({"status": "error"}, None),
    ],
)
async def test_coordinator_reads_homestatus(hass, response, expected):
    """Coordinator calls homestatus for every home and parses the result."""
    client = MagicMock()
    client._post = AsyncMock(return_value=response)
    coordinator = VaillantCoordinator(hass, client)
    result = await coordinator._async_get_boiler_errors([SimpleNamespace(id="home1")])
    assert result == expected
    client._post.assert_awaited_once_with("api/homestatus", json={"home_id": "home1"})


async def test_coordinator_homestatus_api_error_is_not_fatal(hass):
    """API errors on homestatus only disable the boiler sensors."""
    from vaillant_netatmo_api import ApiException

    client = MagicMock()
    client._post = AsyncMock(
        side_effect=ApiException(
            "boom",
            httpx.Request("POST", "https://app.netatmo.net/api/homestatus"),
            None,
        )
    )
    coordinator = VaillantCoordinator(hass, client)
    assert (
        await coordinator._async_get_boiler_errors([SimpleNamespace(id="home1")])
        is None
    )
