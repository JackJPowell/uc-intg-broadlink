"""
Media-player entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import rm
import ucapi
from config_manager import BroadlinkConfig
from ucapi import EntityTypes, media_player
from ucapi.media_player import DeviceClasses, States
from ucapi_framework import create_entity_id
from ucapi_framework.entities import MediaPlayerEntity

_LOG = logging.getLogger(__name__)

features = [
    media_player.Features.SELECT_SOURCE,
    media_player.Features.SELECT_SOUND_MODE,
]


class BroadlinkMediaPlayer(MediaPlayerEntity):
    """Representation of a Broadlink MediaPlayer entity."""

    def __init__(self, config_device: BroadlinkConfig, device: rm.Broadlink):
        """Initialize the class."""
        self._device = device
        _LOG.debug("Broadlink Media Player init")
        super().__init__(
            create_entity_id(EntityTypes.MEDIA_PLAYER, config_device.identifier),
            config_device.name,
            features,
            attributes={
                media_player.Attributes.STATE: States.UNKNOWN,
                media_player.Attributes.SOURCE: "",
                media_player.Attributes.SOURCE_LIST: [],
            },
            device_class=DeviceClasses.RECEIVER,
            options={media_player.Options.SIMPLE_COMMANDS: []},
            cmd_handler=self.media_player_cmd_handler,
        )
        if device is not None:
            self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        """Sync entity state from device to Remote."""
        if self._device is None:
            return
        dev_state = self._device.get_state()
        self.update(
            {
                media_player.Attributes.STATE: dev_state.state,
                media_player.Attributes.SOURCE_LIST: dev_state.source_list,
                media_player.Attributes.MEDIA_TITLE: dev_state.media_title,
                media_player.Attributes.MEDIA_ARTIST: dev_state.media_artist,
            }
        )

    # pylint: disable=too-many-statements
    async def media_player_cmd_handler(
        self,
        entity: MediaPlayerEntity,
        cmd_id: str,
        params: dict[str, Any] | None = None,
        _options: Any | None = None,
    ) -> ucapi.StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param entity: media-player entity
        :param cmd_id: command
        :param params: optional command parameters
        :param options: optional command options
        :return: status code of the command. StatusCodes.OK if the command succeeded.
        """
        if self._device is None:
            _LOG.warning("No Broadlink instance for entity: %s", entity.id)
            return ucapi.StatusCodes.SERVICE_UNAVAILABLE

        _LOG.info(
            "Got %s command request: %s %s", entity.id, cmd_id, params if params else ""
        )

        try:
            match cmd_id:
                case media_player.Commands.SELECT_SOURCE:
                    await self._device.send_command(
                        predefined_code=params.get("source") if params else None
                    )
                case media_player.Commands.SELECT_SOUND_MODE:
                    pass
                # --- simple commands ---

        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST
        return ucapi.StatusCodes.OK
