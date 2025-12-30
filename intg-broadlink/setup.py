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

_LOG = logging.getLogger(__name__)


_MANUAL_INPUT_SCHEMA = RequestUserInput(
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
        return _MANUAL_INPUT_SCHEMA

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> BroadlinkConfig | SetupError | RequestUserInput:
        address = input_values["address"]

        if address is None or address == "":
            return _MANUAL_INPUT_SCHEMA

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
