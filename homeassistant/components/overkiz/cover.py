"""Support for Overkiz covers - shutters etc."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from xmlrpc.client import boolean

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState, UIClass
from pyoverkiz.models import Device

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .entity import OverkizDescriptiveEntity


def is_closed(device: Device) -> boolean:
    """Return if the cover is closed."""

    if state := device.states[OverkizState.CORE_OPEN_CLOSED]:
        return state.value == OverkizCommandParam.CLOSED

    return False


@dataclass
class OverkizCoverDescriptionMixin:
    """Define an entity description mixin for cover entities."""

    open_command: OverkizCommand
    close_command: OverkizCommand
    stop_command: OverkizCommand


@dataclass
class OverkizCoverDescription(CoverEntityDescription, OverkizCoverDescriptionMixin):
    """Class to describe an Overkiz cover."""

    current_position_state: OverkizState | None = None
    invert_position: boolean = True
    set_position_command: OverkizCommand | None = None
    is_closed_fn: Callable[[Device], bool] | None = None


COVER_DESCRIPTIONS: list[OverkizCoverDescription] = [
    OverkizCoverDescription(
        key=UIClass.AWNING,
        current_position_state=OverkizState.CORE_DEPLOYMENT,
        set_position_command=OverkizCommand.SET_DEPLOYMENT,
        open_command=OverkizCommand.DEPLOY,
        close_command=OverkizCommand.UNDEPLOY,
        invert_position=False,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.ROLLER_SHUTTER,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
]

SUPPORTED_DEVICES = {description.key: description for description in COVER_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Overkiz covers from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[OverkizCover] = []

    for device in data.platforms[Platform.COVER]:
        if description := SUPPORTED_DEVICES.get(device.widget) or SUPPORTED_DEVICES.get(
            device.ui_class
        ):
            entities.append(
                OverkizCover(
                    device.device_url,
                    data.coordinator,
                    description,
                )
            )

    async_add_entities(entities)


class OverkizCover(OverkizDescriptiveEntity, CoverEntity):
    """Representation of an Overkiz Cover."""

    entity_description: OverkizCoverDescription

    @property
    def is_closed(self) -> boolean | None:
        """Return if the cover is closed."""

        if is_closed_fn := self.entity_description.is_closed_fn:
            return is_closed_fn(self.device)
        return None

    @property
    def current_cover_position(self) -> int | None:
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        state_name = self.entity_description.current_position_state

        if not state_name:
            return None

        if state := self.device.states[state_name]:
            position = cast(int, state.value)

        if self.entity_description.invert_position:
            position = 100 - position

        return position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self.entity_description.invert_position:
            position = 100 - position

        if command := self.entity_description.set_position_command:
            await self.executor.async_execute_command(command, position)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if command := self.entity_description.open_command:
            await self.executor.async_execute_command(command)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if command := self.entity_description.close_command:
            await self.executor.async_execute_command(command)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if command := self.entity_description.stop_command:
            await self.executor.async_execute_command(command)
