"""
Remote entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
import re
from typing import Any

from config_manager import BroadlinkConfig
from ir_converter import convert_to_broadlink, pulses_to_broadlink_data
from rm import Broadlink
from ucapi import StatusCodes, ir_emitter
from ucapi.entity import EntityTypes
from ucapi.media_player import States as MediaStates
from ucapi.remote import Commands
from ucapi.remote import States as RemoteStates
from ucapi_framework import create_entity_id
from ucapi_framework.entities import IREmitterEntity
from unfurled import Remote

_LOG = logging.getLogger(__name__)

BROADLINK_REMOTE_STATE_MAPPING = {
    MediaStates.UNKNOWN: RemoteStates.UNKNOWN,
    MediaStates.UNAVAILABLE: RemoteStates.UNAVAILABLE,
    MediaStates.OFF: RemoteStates.OFF,
    MediaStates.ON: RemoteStates.ON,
    MediaStates.STANDBY: RemoteStates.OFF,
    MediaStates.PLAYING: RemoteStates.ON,
}


class BroadlinkIREmitter(IREmitterEntity):
    """Representation of a Broadlink IR Emitter entity."""

    def __init__(self, config_device: BroadlinkConfig, device: Broadlink):
        """Initialize the class."""
        self._device = device
        self._remote_address = config_device.remote_address
        self._remote_api_key = config_device.remote_api_key
        _LOG.debug("Broadlink IR Emitter init")
        super().__init__(
            create_entity_id(EntityTypes.IR_EMITTER, config_device.identifier),
            f"{config_device.name} IR Emitter",
            [ir_emitter.Features.SEND_IR],
            attributes={
                ir_emitter.Attributes.STATE: ir_emitter.States.UNKNOWN,
            },
            options={
                ir_emitter.Options.IR_FORMATS: ["PRONTO", "HEX"],
                ir_emitter.Options.PORTS: [{"id": "main", "name": "Main"}],
            },
            cmd_handler=self.command_handler,
        )
        if device is not None:
            self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        """Sync entity state from device to Remote."""
        if self._device is None:
            return
        dev_state = self._device.get_state()
        mapped = BROADLINK_REMOTE_STATE_MAPPING.get(
            dev_state.state, RemoteStates.UNKNOWN
        )
        self.update({ir_emitter.Attributes.STATE: mapped})

    def get_int_param(self, param: str, params: dict[str, Any], default: int):
        """Get parameter in integer format."""
        try:
            value = params.get(param, default)
        except AttributeError:
            return default

        if isinstance(value, str) and len(value) > 0:
            return int(float(value))
        return default

    async def command_handler(
        self,
        _entity: IREmitterEntity,
        cmd_id: str,
        params: dict[str, Any] | None = None,
        _options: Any | None = None,
    ) -> StatusCodes:
        """
        Remote entity command handler.

        Called by the integration-API if a command is sent to a configured remote entity.

        :param entity: IR emitter entity
        :param cmd_id: command
        :param params: optional command parameters
        :param options: optional command options
        :return: status code of the command request
        """
        repeat = 1
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._device is None:
            _LOG.warning("No Broadlink instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE

        if params:
            repeat = self.get_int_param("repeat", params, 1)

        try:
            for _i in range(0, repeat):
                await self.handle_command(cmd_id, params)
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return StatusCodes.BAD_REQUEST
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
            code_param = params.get("code") if params else None
            if code_param:
                code = await self._convert_ir_code(code_param)
                return await self._device.send_command(code=code)
            return StatusCodes.BAD_REQUEST

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

    async def _convert_ir_code(self, code: Any) -> bytes:
        """Convert IR input, delegating Remote-supported formats when possible."""
        remote_format = self._get_remote_ir_format(code)
        if self._remote_api_key and self._remote_address and remote_format:
            remote = Remote(self._remote_address, api_key=self._remote_api_key)
            try:
                converted = await remote.ir.convert(code, format=remote_format)
                raw = converted.get("raw")
                if not isinstance(raw, list) or not all(
                    isinstance(timing, int) and not isinstance(timing, bool)
                    for timing in raw
                ):
                    raise ValueError("Remote returned invalid raw IR timings")
                return pulses_to_broadlink_data(raw)
            finally:
                await remote.close()

        return convert_to_broadlink(code)

    @staticmethod
    def _get_remote_ir_format(code: Any) -> str | None:
        """Return the Remote conversion format for supported IR input."""
        if not isinstance(code, str):
            return None

        normalized = code.strip()
        if normalized.startswith("0000"):
            return "PRONTO"
        if re.fullmatch(r"\d+;0x[0-9A-Fa-f]+;\d+;\d+", normalized):
            return "HEX"
        return None

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
