"""
Remote entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any
from enum import Enum
from config import BroadlinkDevice, create_entity_id
from ucapi import StatusCodes, Entity
from ucapi.media_player import States as MediaStates
from ucapi.remote import Attributes, Commands
from ucapi.remote import States as RemoteStates
import rm
from ir_converter import convert_to_broadlink

_LOG = logging.getLogger(__name__)

BROADLINK_REMOTE_STATE_MAPPING = {
    MediaStates.UNKNOWN: RemoteStates.UNKNOWN,
    MediaStates.UNAVAILABLE: RemoteStates.UNAVAILABLE,
    MediaStates.OFF: RemoteStates.OFF,
    MediaStates.ON: RemoteStates.ON,
    MediaStates.STANDBY: RemoteStates.OFF,
    MediaStates.PLAYING: RemoteStates.ON,
}


class EntityTypes(str, Enum):
    """Entity types."""

    IR_EMITTER = "ir_emitter"


class BroadlinkIREmitter(Entity):
    """Representation of a Broadlink IR Emitter entity."""

    def __init__(self, config_device: BroadlinkDevice, device: rm.Broadlink):
        """Initialize the class."""
        self._device: rm.Broadlink = device
        _LOG.debug("Broadlink IR Emitter init")
        entity_id = create_entity_id(config_device.identifier, "ir_emitter")
        features = ["send_ir"]
        super().__init__(
            entity_id,
            f"{config_device.name} IR Emitter",
            EntityTypes.IR_EMITTER,
            features,
            attributes={
                Attributes.STATE: device.state,
            },
            options={
                "ir_formats": ["PRONTO", "HEX"],
                "ports": [{"id": "main", "name": "Main"}],
            },
            cmd_handler=self.command,
        )

    def get_int_param(self, param: str, params: dict[str, Any], default: int):
        """Get parameter in integer format."""
        try:
            value = params.get(param, default)
        except AttributeError:
            return default

        if isinstance(value, str) and len(value) > 0:
            return int(float(value))
        return default

    async def command(
        self, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        """
        Remote entity command handler.

        Called by the integration-API if a command is sent to a configured remote entity.

        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command request
        """
        repeat = 1
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._device is None:
            _LOG.warning("No Broadlink instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE

        if params:
            repeat = self.get_int_param("repeat", params, 1)

        for _i in range(0, repeat):
            await self.handle_command(cmd_id, params)
        return StatusCodes.OK

    async def handle_command(
        self, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        """Handle command."""
        if params is None:
            return StatusCodes.BAD_REQUEST

        if params:
            repeat = self._get_int_param("repeat", params, 1)
        else:
            repeat = 1

        if cmd_id == "send_ir":
            code = convert_to_broadlink(params.get("code"))
            await self._device.send_command(code=code)
            return StatusCodes.OK

        if cmd_id == "stop_ir":
            # Ignore stop command as Broadlink does not support it
            return StatusCodes.OK

        if cmd_id == Commands.SEND_CMD_SEQUENCE:
            success = True
            for command in params.get("sequence", []):
                for _ in range(0, repeat):
                    command_or_status = self._get_command_or_status_code(
                        cmd_id, command
                    )
                    if isinstance(command_or_status, StatusCodes):
                        success = False
                    else:
                        res = await self._device.send_command(code=command_or_status)
                        if res != StatusCodes.OK:
                            success = False
            if success:
                return StatusCodes.OK
            return StatusCodes.BAD_REQUEST

        # send "raw" commands as is to the receiver
        return await self._device.send_command(code=cmd_id)

    @staticmethod
    def _get_command_or_status_code(cmd_id: str, command: str) -> str | StatusCodes:
        if not command:
            _LOG.error("Command parameter is missing for cmd_id %s", cmd_id)
            return StatusCodes.BAD_REQUEST
        if command.startswith("remote."):
            _LOG.error("Command %s is not allowed for cmd_id %s.", command, cmd_id)
            return StatusCodes.BAD_REQUEST
        return command

    @staticmethod
    def _get_int_param(param: str, params: dict[str, Any], default: int) -> int:
        try:
            value = params.get(param, default)
        except AttributeError:
            return default

        if isinstance(value, str) and len(value) > 0:
            return int(float(value))
        return default
