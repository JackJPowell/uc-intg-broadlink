"""
Setup flow for Broadlink Remote integration.

:copyright: (c) 2025 Jack Powell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import broadlink
from broadlink.exceptions import NetworkTimeoutError
from config_manager import BroadlinkConfig
from ucapi import (
    IntegrationSetupError,
    RequestUserInput,
    SetupError,
)
from ucapi_framework import BaseSetupFlow
from unfurled import Remote, discover_remotes

_LOG = logging.getLogger(__name__)


class BroadlinkSetupFlow(BaseSetupFlow[BroadlinkConfig]):
    """
    Setup flow for Broadlink integration.

    Handles Broadlink device configuration through Broadlink protocol discovery or manual entry.
    """

    def get_manual_entry_form(self) -> RequestUserInput:
        """
        Return the manual entry form for device setup.

        :return: RequestUserInput with form fields for manual configuration
        """
        return RequestUserInput(
            {"en": "Broadlink Setup"},
            [
                {
                    "id": "info",
                    "label": {
                        "en": "Setup Information",
                    },
                    "field": {
                        "label": {
                            "value": {
                                "en": (
                                    "Please supply the following settings for your Broadlink device."
                                ),
                            }
                        }
                    },
                },
                {
                    "field": {"text": {"value": ""}},
                    "id": "address",
                    "label": {
                        "en": "IP Address",
                    },
                },
            ],
        )

    async def get_additional_configuration_screen(
        self,
        device_config: BroadlinkConfig,
        previous_input: dict[str, Any],
        error_message: str | None = None,
    ) -> RequestUserInput:
        """Discover a Remote, then request its PIN for temporary authentication."""
        try:
            remotes = await discover_remotes()
        except Exception as err:  # pylint: disable=broad-except
            _LOG.warning(
                "Remote discovery failed; allowing manual address entry: %s", err
            )
            remotes = []
        pin_field = {
            "id": "remote_pin",
            "label": {"en": "Remote PIN"},
            "field": {"password": {"value": ""}},
        }
        error_field = (
            [
                {
                    "id": "authentication_error",
                    "label": {"en": "Authentication failed"},
                    "field": {"label": {"value": {"en": error_message}}},
                }
            ]
            if error_message
            else []
        )

        if remotes:
            remote_items = [
                {
                    "id": remote.api_url,
                    "label": {
                        "en": f"{remote.name.split('-', maxsplit=1)[0]} ({remote.host})"
                    },
                }
                for remote in remotes
            ]
            return RequestUserInput(
                {"en": "Remote API access"},
                error_field
                + [
                    {
                        "id": "remote_address",
                        "label": {"en": "Remote"},
                        "field": {
                            "dropdown": {
                                "value": remote_items[0]["id"],
                                "items": remote_items,
                            }
                        },
                    },
                    pin_field,
                ],
            )

        _LOG.info("No Unfolded Circle Remotes discovered; requesting manual address")
        return RequestUserInput(
            {"en": "Remote API access"},
            error_field
            + [
                {
                    "id": "remote_address",
                    "label": {"en": "Remote API Address"},
                    "field": {
                        "text": {
                            "value": device_config.remote_address or "",
                        }
                    },
                },
                pin_field,
            ],
        )

    async def handle_additional_configuration_response(
        self, msg: Any
    ) -> SetupError | RequestUserInput | None:
        """Create and retain a Remote API key; never persist the supplied PIN."""
        if self._pending_device_config is None:
            return SetupError(error_type=IntegrationSetupError.OTHER)

        remote_address = str(msg.input_values.get("remote_address", "")).strip()
        pin = str(msg.input_values.get("remote_pin", "")).strip()
        if not remote_address or not pin:
            _LOG.warning("Remote API address or PIN was not supplied")
            return await self.get_additional_configuration_screen(
                self._pending_device_config, msg.input_values
            )

        remote = Remote(remote_address, pin=pin)
        try:
            self._pending_device_config.remote_api_key = await remote.auth.generate_key(
                "broadlink_integration"
            )
            self._pending_device_config.remote_address = remote_address
        except Exception as err:  # pylint: disable=broad-except
            _LOG.warning("Unable to create Remote API key: %s", err)
            return await self.get_additional_configuration_screen(
                self._pending_device_config,
                msg.input_values,
                (
                    "Unable to authenticate with the Remote: "
                    f"{err}. Check the selected Remote and PIN, then try again."
                ),
            )
        finally:
            await remote.close()

        return None

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> BroadlinkConfig | SetupError | RequestUserInput:
        address = input_values["address"]

        if address is None or address == "":
            return self.get_manual_entry_form()

        _LOG.debug("Connecting to Broadlink device at %s", address)

        device = None
        try:
            # Try xdiscover first (exits early when device found)
            _LOG.debug("Attempting xdiscover at %s", address)
            try:
                for discovered in broadlink.xdiscover(
                    discover_ip_address=address, timeout=5
                ):
                    _LOG.debug("Device discovered: %s", discovered)
                    device = discovered
                    break  # Found a device at the target IP, exit early
            except NetworkTimeoutError as timeout_err:
                _LOG.debug("Discovery timed out: %s", timeout_err)
            except Exception as disc_err:
                _LOG.debug("Discovery failed: %s", disc_err)

            if not device:
                # Fallback to hello method
                _LOG.debug("Discovery returned no device, trying hello method")
                try:
                    device = broadlink.hello(ip_address=address, timeout=5)
                    if device:
                        _LOG.debug("Device connected via hello: %s", device)
                except NetworkTimeoutError as timeout_err:
                    _LOG.warning("Hello timed out for %s: %s", address, timeout_err)
                except Exception as hello_err:
                    _LOG.warning("Hello failed for %s: %s", address, hello_err)

            if not device:
                _LOG.error(
                    "No devices found at IP address %s (both discovery and hello failed)",
                    address,
                )
                return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

            device.auth()
            _LOG.info(
                "Broadlink device authenticated: %s", device
            )  # Get device MAC address as identifier
            identifier = device.mac.hex() if hasattr(device, "mac") else None
            if not identifier:
                _LOG.error("Device missing MAC address")
                return SetupError(error_type=IntegrationSetupError.OTHER)

            # Get device name or use type as fallback
            device_name = (
                device.name
                if hasattr(device, "name") and device.name
                else f"Broadlink {device.type}"
            )

            # if we are adding a new device: make sure it's not already configured
            if self._add_mode and self.config.contains(identifier):
                _LOG.info(
                    "Skipping found device %s: already configured",
                    device_name,
                )
                return SetupError(IntegrationSetupError.OTHER)

            # Create config object
            config = BroadlinkConfig(
                identifier=identifier,
                name=device_name,
                address=address,
                data={},
            )

            # Clear device reference before returning to avoid any cleanup issues
            device = None

            _LOG.debug("Returning config for device %s", device_name)
            return config

        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("Setup Error: %s", err, exc_info=True)
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)
