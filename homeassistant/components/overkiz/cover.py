"""Support for Overkiz covers - shutters etc."""
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast
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
    return device.states[OverkizState.CORE_OPEN_CLOSED] == OverkizCommandParam.CLOSED


@dataclass
class OverkizCoverDescription(CoverEntityDescription):
    """Class to describe an Overkiz cover."""

    ui_class: UIClass = None
    current_position_state: OverkizState = None
    invert_position: boolean = True
    set_position_command: OverkizCommand = None
    open_command: OverkizCommand = None
    close_command: OverkizCommand = None
    is_closed_fn: Callable[[Device], bool] = None
    stop_command: OverkizCommand = None


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

    @property
    def is_closed(self) -> Optional[boolean]:
        self.entity_description.is_closed_fn(self.device)

    @property
    def current_cover_position(self) -> Optional[int]:
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = None
        if current_state := self.device.states[
            self.entity_description.current_position_state
        ]:
            position = current_state.value

        if self.entity_description.invert_position:
            position = 100 - position

        return cast(int, position)

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
