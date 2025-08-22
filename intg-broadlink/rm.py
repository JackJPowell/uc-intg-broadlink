"""
This module implements the broadlink communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from base64 import b64decode, b64encode
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum
from typing import ParamSpec, TypeVar

import broadlink
import config as BroadlinkConfig
from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from config import BroadlinkDevice
from pyee.asyncio import AsyncIOEventEmitter
from ucapi import StatusCodes
from ir_converter import custom_to_broadlink, hex_to_broadlink, pronto_to_broadlink


_LOG = logging.getLogger(__name__)

BACKOFF_MAX = 30
BACKOFF_SEC = 2

LEARNING_TIMEOUT = timedelta(seconds=30)


class EVENTS(IntEnum):
    """Internal driver events."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    PAIRED = 3
    ERROR = 4
    UPDATE = 5


_BroadlinkDeviceT = TypeVar("_BroadlinkDeviceT", bound="BroadlinkDevice")
_P = ParamSpec("_P")


class PowerState(StrEnum):
    """Playback state for companion protocol."""

    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"


class Broadlink:
    """Representing a Broadlink Device."""

    def __init__(
        self, device: BroadlinkDevice, loop: AbstractEventLoop | None = None
    ) -> None:
        """Create instance."""
        self._loop: AbstractEventLoop = loop or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self._loop)
        self._is_connected: bool = False
        self._broadlink: broadlink | None = None
        self._device: BroadlinkDevice = device
        self._state: PowerState = PowerState.OFF
        self._source_list: list[str] = []
        self._source: str | None = None

    @property
    def device_config(self) -> BroadlinkDevice:
        """Return the device configuration."""
        return self._device

    @property
    def identifier(self) -> str:
        """Return the device identifier."""
        if not self._device.identifier:
            raise ValueError("Instance not initialized, no identifier available")
        return self._device.identifier

    @property
    def log_id(self) -> str:
        """Return a log identifier."""
        return self._device.name if self._device.name else self._device.identifier

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device.name

    @property
    def address(self) -> str | None:
        """Return the optional device address."""
        return self._device.address

    @property
    def state(self) -> PowerState | None:
        """Return the device state."""
        return self._state.upper()

    @property
    def source(self) -> str | None:
        """Return the device source."""
        return self._source

    @property
    def source_list(self) -> list[str]:
        """Return the device source list."""
        return self._source_list

    async def connect(self) -> None:
        """Establish connection to the AVR."""
        if self.state != PowerState.OFF:
            return

        _LOG.debug("[%s] Connecting to device", self.log_id)
        self.events.emit(EVENTS.CONNECTING, self._device.identifier)
        await self._connect_setup()

    async def _connect_setup(self) -> None:
        try:
            await self._connect()

            if self.state != PowerState.OFF:
                _LOG.debug("[%s] Device is alive", self.log_id)
                self.reload_sources()
                self.events.emit(
                    EVENTS.UPDATE,
                    self._device.identifier,
                    {
                        "state": self.state,
                        "source_list": self.source_list,
                        "title": "",
                        "artist": "",
                    },
                )
            else:
                _LOG.debug("[%s] Device is not alive", self.log_id)
                self.events.emit(
                    EVENTS.UPDATE,
                    self._device.identifier,
                    {"state": PowerState.OFF},
                )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Could not connect: %s", self.log_id, err)

        self.events.emit(EVENTS.CONNECTED, self._device.identifier)
        _LOG.debug("[%s] Connected", self.log_id)

    async def _connect(self) -> None:
        """Connect to the device."""
        _LOG.debug(
            "[%s] Connecting to TVWS device at IP address: %s",
            self.log_id,
            self.address,
        )
        try:
            devices = broadlink.xdiscover(
                discover_ip_address=self._device.address, timeout=1
            )
            for self._broadlink in devices:
                self._broadlink.auth()
                self._broadlink.hello()
                self._state = PowerState.ON
                if not self._broadlink:
                    self._state = PowerState.OFF
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Connection error: %s", self.log_id, err)
            self._state = PowerState.OFF

    async def send_command(self, predefined_code: str = None, code: str = None) -> str:
        """Send a command to the Broadlink."""
        update = {}
        self.events.emit(
            EVENTS.UPDATE,
            self._device.identifier,
            {
                "title": "",
                "artist": "",
            },
        )
        if predefined_code:
            device, command = predefined_code.split(":")
            code = BroadlinkConfig.devices.get_code(
                self._device.identifier, device.lower(), command.lower()
            )
            if not code:
                self.emit(device, command, "Not Found")
                return StatusCodes.NOT_FOUND

            try:
                self._broadlink.send_data(b64decode(code))

                self.emit(device, command, "Sent")
                return StatusCodes.OK
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.error(
                    "[%s] Error sending command %s: %s",
                    self.log_id,
                    command,
                    err,
                )
                raise Exception(err) from err
        elif code:
            try:
                self._broadlink.send_data(self._broadlink.encrypt(code))
                return StatusCodes.OK
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.error(
                    "[%s] Error sending custom command: %s",
                    self.log_id,
                    err,
                )
                raise Exception(err) from err

    def convert_ir_code(self, code: str, code_type: str = "auto") -> str:
        """
        Convert HEX or PRONTO IR codes to Broadlink format.

        Args:
            code: IR code string (HEX or PRONTO format)
            code_type: Type of code ("hex", "pronto", or "auto" for auto-detection)

        Returns:
            str: Base64 encoded Broadlink IR code

        Raises:
            ValueError: If code format is invalid or conversion functions not available
        """
        code = code.strip()
        if not code:
            raise ValueError("IR code cannot be empty")

        # Auto-detect code type if not specified
        if code_type == "auto" or code_type is None:
            if code.startswith("0000 ") or " " in code:
                code_type = "pronto"
            else:
                code_type = "hex"

        try:
            if code_type.lower() == "hex":
                if ";" in code:
                    broadlink_data = custom_to_broadlink(code)
                else:
                    broadlink_data = hex_to_broadlink(code)
            elif code_type.lower() == "pronto":
                broadlink_data = pronto_to_broadlink(code)
            else:
                raise ValueError(f"Unsupported code type: {code_type}")

            return broadlink_data

        except Exception as e:
            _LOG.error("[%s] Error converting IR code: %s", self.log_id, e)
            raise ValueError(f"Failed to convert IR code: {e}") from e

    async def learn_ir_command(self, input: str) -> None:
        """Learn a command."""
        _, mode, device, command = input.split(":")
        self.emit(device, command, "Press the button on the remote...")
        try:
            self._broadlink.enter_learning()
        except (BroadlinkException, OSError) as err:
            _LOG.error("[%s] Error learning command %s: %s", self.log_id, input, err)
            return StatusCodes.SERVER_ERROR

        try:
            start_time = datetime.now(tz=UTC)
            while (datetime.now(tz=UTC) - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                try:
                    code = self._broadlink.check_data()
                    if not code:
                        continue
                except (ReadError, StorageError):
                    continue
                b64_code = b64encode(code).decode("utf8")
                status = BroadlinkConfig.devices.append_code(
                    self._device.identifier,
                    device.lower(),
                    command.lower(),
                    b64_code,
                )

                self.reload_sources()
                self.emit(device, command, status, include_source_list=True)
                return StatusCodes.OK

            self.emit(device, command, "Timeout", include_source_list=True)
            return StatusCodes.TIMEOUT

        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error learning command %s: %s", self.log_id, input, err)
            return StatusCodes.SERVER_ERROR

    async def learn_rf_command(self, input: str) -> None:
        """Learn a radiofrequency command."""
        frequency = None
        status = "Learned"
        count = input.count(":")
        if count == 3:
            _, _, device, command = input.split(":")
        elif count == 4:
            _, _, device, command, frequency = input.split(":")
        else:
            _LOG.error(
                "[%s] Invalid input format for learning RF command: %s",
                self.log_id,
                input,
            )
            return StatusCodes.BAD_REQUEST

        if not frequency:
            self.emit(device, command, "Hold the button on the remote...")
            await asyncio.sleep(2)

            try:
                self._broadlink.sweep_frequency()

            except (BroadlinkException, OSError) as err:
                _LOG.debug("Failed to sweep frequency: %s", err)
                return StatusCodes.SERVER_ERROR

            try:
                start_time = datetime.now(tz=UTC)
                while (datetime.now(tz=UTC) - start_time) < LEARNING_TIMEOUT:
                    await asyncio.sleep(2)
                    is_found, frequency = self._broadlink.check_frequency()
                    if is_found:
                        _LOG.debug("Radio frequency detected: %s MHz", frequency)
                        self.emit(device, command, f"Found frequency: {frequency} MHz")
                        self._broadlink.cancel_sweep_frequency()
                        break
                    else:
                        _LOG.debug("Detecting: %s MHz", frequency)
                        self.emit(
                            device, command, f"Detecting frequency: {frequency} MHz"
                        )
                else:
                    self._broadlink.cancel_sweep_frequency()
                    self.emit(device, command, "Failed to find frequency")
                    return StatusCodes.TIMEOUT

            except (BroadlinkException, OSError) as err:
                _LOG.debug("Failed to check frequency: %s", err)
                return StatusCodes.SERVER_ERROR

            await asyncio.sleep(2)

        self.emit(device, command, f"Single press the button: ({frequency} MHz)")

        try:
            self._broadlink.find_rf_packet(frequency=float(frequency))

        except (BroadlinkException, OSError) as err:
            _LOG.debug("Failed to enter learning mode: %s", err)
            return StatusCodes.SERVER_ERROR

        try:
            start_time = datetime.now(tz=UTC)
            while (datetime.now(tz=UTC) - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(2)
                try:
                    code = self._broadlink.check_data()
                except (ReadError, StorageError) as err:
                    _LOG.debug("No RF code received yet, retrying: %s", err)
                    self.emit(
                        device,
                        command,
                        f"Keep single pressing the button: ({frequency} MHz)",
                    )
                    continue
                _LOG.debug("RF code learned: %s", code)
                self.emit(device, command, "RF Code learned")
                b64_code = b64encode(code).decode("utf8")
                status = BroadlinkConfig.devices.append_code(
                    self._device.identifier,
                    device.lower(),
                    command.lower(),
                    b64_code,
                )

                self.reload_sources()
                self.emit(device, command, status, include_source_list=True)
                return StatusCodes.OK

            self.emit(device, command, "Timeout", include_source_list=True)
            return StatusCodes.TIMEOUT

        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error learning command %s: %s", self.log_id, input, err)
            return StatusCodes.SERVER_ERROR

    async def remove_command(self, input: str) -> None:
        """Remove a command."""
        command = ""
        device = input
        if ":" in input:
            device, command = input.split(":")
        status = BroadlinkConfig.devices.remove_code(
            self._device.identifier, device.lower(), command.lower()
        )
        self.events.emit(
            EVENTS.UPDATE,
            self._device.identifier,
            {
                "title": f"{device}:{command}",
                "artist": status,
            },
        )

        self.reload_sources()
        return StatusCodes.OK

    def reload_sources(self) -> None:
        """Reload the sources for the device."""
        _LOG.debug("[%s] Reloading sources for device", self.log_id)
        self._source_list.clear()
        for name, command in self._device.data.items():
            for cmd_name, _ in command.items():
                self._source_list.append(f"{name}:{cmd_name}")

    def emit(self, device, command, message, include_source_list=False) -> None:
        """Emit an event."""
        data = {
            "title": f"{device}:{command}",
            "artist": message,
        }
        if include_source_list:
            data["source_list"] = self.source_list

        self.events.emit(
            EVENTS.UPDATE,
            self._device.identifier,
            data,
        )
