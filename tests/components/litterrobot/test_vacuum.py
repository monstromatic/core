"""Test the Litter-Robot vacuum entity."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.components.litterrobot.entity import REFRESH_WAIT_TIME_SECONDS
from homeassistant.components.litterrobot.vacuum import SERVICE_SET_SLEEP_MODE
from homeassistant.components.vacuum import (
    ATTR_STATUS,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_DOCKED,
    STATE_ERROR,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.util.dt import utcnow

from .common import VACUUM_ENTITY_ID
from .conftest import setup_integration

from tests.common import async_fire_time_changed

VACUUM_UNIQUE_ID_OLD = "LR3C012345-Litter Box"
VACUUM_UNIQUE_ID_NEW = "LR3C012345-litter_box"

COMPONENT_SERVICE_DOMAIN = {
    SERVICE_SET_SLEEP_MODE: DOMAIN,
}


async def test_vacuum(hass: HomeAssistant, mock_account: MagicMock) -> None:
    """Tests the vacuum entity was set up."""
    ent_reg = er.async_get(hass)

    # Create entity entry to migrate to new unique ID
    ent_reg.async_get_or_create(
        PLATFORM_DOMAIN,
        DOMAIN,
        VACUUM_UNIQUE_ID_OLD,
        suggested_object_id=VACUUM_ENTITY_ID.replace(PLATFORM_DOMAIN, ""),
    )
    ent_reg_entry = ent_reg.async_get(VACUUM_ENTITY_ID)
    assert ent_reg_entry.unique_id == VACUUM_UNIQUE_ID_OLD

    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_SLEEP_MODE)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED
    assert vacuum.attributes["is_sleeping"] is False

    ent_reg_entry = ent_reg.async_get(VACUUM_ENTITY_ID)
    assert ent_reg_entry.unique_id == VACUUM_UNIQUE_ID_NEW


async def test_vacuum_status_when_sleeping(
    hass: HomeAssistant, mock_account_with_sleeping_robot: MagicMock
) -> None:
    """Tests the vacuum status when sleeping."""
    await setup_integration(hass, mock_account_with_sleeping_robot, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.attributes.get(ATTR_STATUS) == "Ready (Sleeping)"


async def test_no_robots(
    hass: HomeAssistant, mock_account_with_no_robots: MagicMock
) -> None:
    """Tests the vacuum entity was set up."""
    await setup_integration(hass, mock_account_with_no_robots, PLATFORM_DOMAIN)

    assert not hass.services.has_service(DOMAIN, SERVICE_SET_SLEEP_MODE)


async def test_vacuum_with_error(
    hass: HomeAssistant, mock_account_with_error: MagicMock
) -> None:
    """Tests a vacuum entity with an error."""
    await setup_integration(hass, mock_account_with_error, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_ERROR


@pytest.mark.parametrize(
    "service,command,extra",
    [
        (SERVICE_START, "start_cleaning", None),
        (SERVICE_TURN_OFF, "set_power_status", None),
        (SERVICE_TURN_ON, "set_power_status", None),
        (
            SERVICE_SET_SLEEP_MODE,
            "set_sleep_mode",
            {"data": {"enabled": True, "start_time": "22:30"}},
        ),
        (SERVICE_SET_SLEEP_MODE, "set_sleep_mode", {"data": {"enabled": True}}),
        (SERVICE_SET_SLEEP_MODE, "set_sleep_mode", {"data": {"enabled": False}}),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    mock_account: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service: str,
    command: str,
    extra: dict[str, Any],
) -> None:
    """Test sending commands to the vacuum."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED

    extra = extra or {}
    data = {ATTR_ENTITY_ID: VACUUM_ENTITY_ID, **extra.get("data", {})}
    deprecated = extra.get("deprecated", False)

    await hass.services.async_call(
        COMPONENT_SERVICE_DOMAIN.get(service, PLATFORM_DOMAIN),
        service,
        data,
        blocking=True,
    )
    future = utcnow() + timedelta(seconds=REFRESH_WAIT_TIME_SECONDS)
    async_fire_time_changed(hass, future)
    getattr(mock_account.robots[0], command).assert_called_once()
    assert (f"'{DOMAIN}.{service}' service is deprecated" in caplog.text) is deprecated
