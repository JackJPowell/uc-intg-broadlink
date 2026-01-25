"""
This module implements the broadlink communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from base64 import b64decode, b64encode
from datetime import UTC, datetime, timedelta

import broadlink
from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from ucapi import EntityTypes, StatusCodes
from ucapi.media_player import Attributes as MediaAttr
from ucapi.media_player import States as PowerState
from ucapi_framework import create_entity_id, BaseIntegrationDriver
from ucapi_framework.device import ExternalClientDevice, DeviceEvents as EVENTS

from config_manager import BroadlinkConfig, BroadlinkConfigManager

_LOG = logging.getLogger(__name__)

LEARNING_TIMEOUT = timedelta(seconds=30)


class Broadlink(ExternalClientDevice):
    """Representing a Broadlink Device."""

    def __init__(
        self,
        device_config: BroadlinkConfig,
        loop: AbstractEventLoop | None = None,
        config_manager: BroadlinkConfigManager | None = None,
        driver: BaseIntegrationDriver | None = None,
    ) -> None:
        """Create instance."""
        super().__init__(
            device_config,
            loop,
            enable_watchdog=False,  # Broadlink doesn't need watchdog
            config_manager=config_manager,
            driver=driver,
        )
        self._device_config: BroadlinkConfig
        self._config_manager: BroadlinkConfigManager  # Type narrowing from base class
        self._state: PowerState = PowerState.OFF
        self._source_list: list[str] = []
        self._source: str | None = None

    @property
    def identifier(self) -> str:
        """Return the device identifier."""
        if not self._device_config.identifier:
            raise ValueError("Instance not initialized, no identifier available")
        return self._device_config.identifier

    @property
    def log_id(self) -> str:
        """Return a log identifier."""
        return (
            self._device_config.name
            if self._device_config.name
            else self._device_config.identifier
        )

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device_config.name

    @property
    def address(self) -> str | None:
        """Return the optional device address."""
        return self._device_config.address

    @property
    def state(self) -> str:
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

    async def create_client(self) -> broadlink.Device:
        """Create and discover the Broadlink client."""
        _LOG.debug(
            "[%s] Creating Broadlink client at IP: %s",
            self.log_id,
            self.address,
        )

        # Try connecting to stored IP address first
        try:
            device = broadlink.hello(ip_address=self._device_config.address, timeout=5)
            if device:
                return device
        except Exception as ip_err:
            _LOG.warning(
                "[%s] Failed to connect to stored IP %s: %s. Trying discovery...",
                self.log_id,
                self._device_config.address,
                ip_err,
            )

        # Fallback: try to discover device by MAC using xdiscover to exit early
        for device in broadlink.xdiscover(timeout=5):
            if hasattr(device, "mac") and device.mac.hex() == self.identifier:
                _LOG.debug(
                    "[%s] Found device with matching MAC: %s",
                    self.log_id,
                    device,
                )
                # Update IP address if it changed
                if hasattr(device, "host") and device.host:
                    new_ip = device.host[0]
                    if new_ip != self._device_config.address:
                        _LOG.info(
                            "[%s] Device discovered at new IP address %s (was %s), updating config",
                            self.log_id,
                            new_ip,
                            self._device_config.address,
                        )
                        self.update_config(address=new_ip)
                return device

        raise Exception(f"Device with MAC {self.identifier} not found on network")

    async def connect_client(self) -> None:
        """Authenticate with the Broadlink device."""
        if not self._client:
            raise Exception("Client not created")

        _LOG.debug("[%s] Authenticating with Broadlink device", self.log_id)
        self._client.auth()  # type: ignore[attr-defined]

        # Verify we connected to the correct device by checking MAC address
        if hasattr(self._client, "mac") and self._client.mac:
            connected_mac = self._client.mac.hex()
            if connected_mac != self.identifier:
                _LOG.error(
                    "[%s] MAC address mismatch! Expected %s, got %s",
                    self.log_id,
                    self.identifier,
                    connected_mac,
                )
                raise ValueError(
                    f"MAC address mismatch: expected {self.identifier}, got {connected_mac}"
                )

            # Check if IP address has changed
            if hasattr(self._client, "host") and self._client.host:
                current_ip = self._client.host[0]
                if current_ip != self._device_config.address:
                    _LOG.warning(
                        "[%s] Device IP address changed from %s to %s, updating config",
                        self.log_id,
                        self._device_config.address,
                        current_ip,
                    )
                    self.update_config(address=current_ip)

        self._state = PowerState.ON
        _LOG.debug("[%s] Device authenticated and ready", self.log_id)
        self.reload_sources()
        self.events.emit(
            EVENTS.UPDATE,
            create_entity_id(EntityTypes.MEDIA_PLAYER, self.identifier),
            {
                MediaAttr.STATE: self.state,
                MediaAttr.SOURCE_LIST: self.source_list,
                MediaAttr.MEDIA_TITLE: "",
                MediaAttr.MEDIA_ARTIST: "",
            },
        )
        self.events.emit(
            EVENTS.UPDATE,
            create_entity_id(EntityTypes.REMOTE, self.identifier),
            {MediaAttr.STATE: "ON"},
        )
        self.events.emit(
            EVENTS.UPDATE,
            create_entity_id(EntityTypes.IR_EMITTER, self.identifier),
            {MediaAttr.STATE: "ON"},
        )

    async def disconnect_client(self) -> None:
        """Disconnect from the Broadlink device."""
        _LOG.debug("[%s] Disconnecting from Broadlink device", self.log_id)
        self._state = PowerState.OFF
        # Broadlink doesn't have an explicit disconnect method
        # The client object will be cleaned up by the parent class

    def check_client_connected(self) -> bool:
        """Check if the Broadlink client is connected."""
        # Broadlink is stateless, so we just check if client exists and state is ON
        return self._client is not None and self._state == PowerState.ON

    async def send_command(
        self, predefined_code: str | None = None, code: str | bytes | None = None
    ) -> StatusCodes:
        """Send a command to the Broadlink."""
        # Ensure we have a valid connection
        if not self.is_connected or not self._client:
            await self.connect()

        self.events.emit(
            EVENTS.UPDATE,
            create_entity_id(EntityTypes.MEDIA_PLAYER, self.identifier),
            {
                MediaAttr.MEDIA_TITLE: "",
                MediaAttr.MEDIA_ARTIST: "",
            },
        )

        if predefined_code:
            device, command = predefined_code.split(":")
            code_data = self._config_manager.get_code(
                self.identifier, device.lower(), command.lower()
            )
            if not code_data:
                self.emit(device, command, "Not Found")
                return StatusCodes.NOT_FOUND

            try:
                decode = b64decode(code_data)
                if self._client:
                    self._client.send_data(decode)  # type: ignore[attr-defined]
                    self.emit(device, command, "Sent")
                    return StatusCodes.OK
                return StatusCodes.SERVER_ERROR
            except (BroadlinkException, OSError) as err:
                _LOG.warning(
                    "[%s] Command failed, attempting reconnect: %s",
                    self.log_id,
                    err,
                )
                # Force reconnection
                await self.disconnect()
                await self.connect()

                # Retry once
                try:
                    if self._client:
                        decode = b64decode(code_data)
                        self._client.send_data(decode)  # type: ignore[attr-defined]
                        self.emit(device, command, "Sent (after reconnect)")
                        return StatusCodes.OK
                except Exception as retry_err:
                    _LOG.error(
                        "[%s] Command failed after reconnect: %s",
                        self.log_id,
                        retry_err,
                    )
                    self.emit(device, command, "Error")
                    return StatusCodes.SERVER_ERROR
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.error(
                    "[%s] Error sending command %s: %s",
                    self.log_id,
                    command,
                    err,
                )
                self.emit(device, command, "Error")
                return StatusCodes.BAD_REQUEST
        elif code:
            try:
                if not self._client:
                    await self.connect()
                if self._client:
                    self._client.send_data(code)  # type: ignore[attr-defined]
                    return StatusCodes.OK
                return StatusCodes.SERVER_ERROR
            except (BroadlinkException, OSError) as err:
                _LOG.warning(
                    "[%s] Custom command failed, attempting reconnect: %s",
                    self.log_id,
                    err,
                )
                # Force reconnection and retry
                await self.disconnect()
                await self.connect()

                try:
                    if self._client:
                        self._client.send_data(code)  # type: ignore[attr-defined]
                        return StatusCodes.OK
                except Exception as retry_err:
                    _LOG.error(
                        "[%s] Custom command failed after reconnect: %s",
                        self.log_id,
                        retry_err,
                    )
                    return StatusCodes.SERVER_ERROR
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.error(
                    "[%s] Error sending custom command: %s",
                    self.log_id,
                    err,
                )
                return StatusCodes.BAD_REQUEST

        return StatusCodes.BAD_REQUEST

    async def learn_ir_command(self, input: str) -> StatusCodes:
        """Learn a command."""
        _, mode, device, command = input.split(":")
        self.emit(device, command, "Press the button on the remote...")

        if not self._client:
            await self.connect()

        if not self._client:
            return StatusCodes.SERVER_ERROR

        try:
            self._client.enter_learning()  # type: ignore[attr-defined]
        except (BroadlinkException, OSError) as err:
            _LOG.error("[%s] Error learning command %s: %s", self.log_id, input, err)
            return StatusCodes.SERVER_ERROR

        try:
            start_time = datetime.now(tz=UTC)
            while (datetime.now(tz=UTC) - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                try:
                    code = self._client.check_data()  # type: ignore[attr-defined]
                    if not code:
                        continue
                except (ReadError, StorageError):
                    continue
                b64_code = b64encode(code).decode("utf8")
                status = self._config_manager.append_code(
                    self.identifier,
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

    async def learn_rf_command(self, input: str) -> StatusCodes:
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

        if not self._client:
            await self.connect()

        if not self._client:
            return StatusCodes.SERVER_ERROR

        if not frequency:
            self.emit(device, command, "Hold the button on the remote...")
            await asyncio.sleep(2)

            try:
                self._client.sweep_frequency()  # type: ignore[attr-defined]

            except (BroadlinkException, OSError) as err:
                _LOG.debug("Failed to sweep frequency: %s", err)
                return StatusCodes.SERVER_ERROR

            try:
                start_time = datetime.now(tz=UTC)
                while (datetime.now(tz=UTC) - start_time) < LEARNING_TIMEOUT:
                    await asyncio.sleep(2)
                    is_found, frequency = self._client.check_frequency()  # type: ignore[attr-defined]
                    if is_found:
                        _LOG.debug("Radio frequency detected: %s MHz", frequency)
                        self.emit(device, command, f"Found frequency: {frequency} MHz")
                        self._client.cancel_sweep_frequency()  # type: ignore[attr-defined]
                        break
                    else:
                        _LOG.debug("Detecting: %s MHz", frequency)
                        self.emit(
                            device, command, f"Detecting frequency: {frequency} MHz"
                        )
                else:
                    self._client.cancel_sweep_frequency()  # type: ignore[attr-defined]
                    self.emit(device, command, "Failed to find frequency")
                    return StatusCodes.TIMEOUT

            except (BroadlinkException, OSError) as err:
                _LOG.debug("Failed to check frequency: %s", err)
                return StatusCodes.SERVER_ERROR

            await asyncio.sleep(2)

        self.emit(device, command, f"Single press the button: ({frequency} MHz)")

        try:
            self._client.find_rf_packet(frequency=float(frequency))  # type: ignore[attr-defined]

        except (BroadlinkException, OSError) as err:
            _LOG.debug("Failed to enter learning mode: %s", err)
            return StatusCodes.SERVER_ERROR

        try:
            start_time = datetime.now(tz=UTC)
            while (datetime.now(tz=UTC) - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(2)
                try:
                    code = self._client.check_data()  # type: ignore[attr-defined]
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
                status = self._config_manager.append_code(
                    self.identifier,
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

    async def remove_command(self, input: str) -> StatusCodes:
        """Remove a command."""
        command = ""
        device = input
        if ":" in input:
            device, command = input.split(":")
        status = self._config_manager.remove_code(
            self.identifier, device.lower(), command.lower()
        )
        self.events.emit(
            EVENTS.UPDATE,
            create_entity_id(EntityTypes.MEDIA_PLAYER, self.identifier),
            {
                MediaAttr.MEDIA_TITLE: f"{device}:{command}",
                MediaAttr.MEDIA_ARTIST: status,
            },
        )

        self.reload_sources()
        return StatusCodes.OK

    def reload_sources(self) -> None:
        """Reload the sources for the device."""
        _LOG.debug("[%s] Reloading sources for device", self.log_id)
        self._source_list.clear()
        for name, command in self._device_config.data.items():
            for cmd_name, _ in command.items():
                self._source_list.append(f"{name}:{cmd_name}")

    def emit(self, device, command, message, include_source_list=False) -> None:
        """Emit an event."""
        data = {
            MediaAttr.MEDIA_TITLE: f"{device}:{command}",
            MediaAttr.MEDIA_ARTIST: message,
        }
        if include_source_list:
            data[MediaAttr.SOURCE_LIST] = self._source_list

        self.events.emit(
            EVENTS.UPDATE,
            create_entity_id(EntityTypes.MEDIA_PLAYER, self.identifier),
            data,
        )
