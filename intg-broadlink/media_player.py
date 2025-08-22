"""
Media-player entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any
import asyncio
import ucapi
import ucapi.api as uc

import rm
from config import BroadlinkDevice, create_entity_id
from ucapi import MediaPlayer, media_player, EntityTypes
from ucapi.media_player import DeviceClasses, Attributes

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

_LOG = logging.getLogger(__name__)
api = uc.IntegrationAPI(_LOOP)
_configured_devices: dict[str, rm.Broadlink] = {}

features = [
    media_player.Features.SELECT_SOURCE,
    media_player.Features.SELECT_SOUND_MODE,
]


class BroadlinkMediaPlayer(MediaPlayer):
    """Representation of a Broadlink MediaPlayer entity."""

    def __init__(self, config_device: BroadlinkDevice, device: rm.Broadlink):
        """Initialize the class."""
        self._device = device
        _LOG.debug("Broadlink Media Player init")
        entity_id = create_entity_id(config_device.identifier, EntityTypes.MEDIA_PLAYER)
        self.config = config_device
        self.options = []
        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes={
                Attributes.STATE: device.state,
                Attributes.SOURCE: device.source if device.source else "",
                Attributes.SOURCE_LIST: device.source_list,
            },
            device_class=DeviceClasses.RECEIVER,
            options={media_player.Options.SIMPLE_COMMANDS: self.options},
            cmd_handler=self.media_player_cmd_handler,
        )

    # pylint: disable=too-many-statements
    async def media_player_cmd_handler(
        self, entity: MediaPlayer, cmd_id: str, params: dict[str, Any] | None
    ) -> ucapi.StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param entity: media-player entity
        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command. StatusCodes.OK if the command succeeded.
        """
        _LOG.info(
            "Got %s command request: %s %s", entity.id, cmd_id, params if params else ""
        )

        try:
            match cmd_id:
                case media_player.Commands.SELECT_SOURCE:
                    await self._device.send_command(
                        predefined_code=params.get("source")
                    )
                case media_player.Commands.SELECT_SOUND_MODE:
                    pass
                # --- simple commands ---

        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST
        return ucapi.StatusCodes.OK


def _get_cmd_param(name: str, params: dict[str, Any] | None) -> str | bool | None:
    if params is None:
        return None
    return params.get(name)
