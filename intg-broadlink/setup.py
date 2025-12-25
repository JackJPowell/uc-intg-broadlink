"""
Setup flow for Broadlink Remote integration.

:copyright: (c) 2025 Jack Powell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import broadlink
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

        try:
            devices = broadlink.discover(discover_ip_address=address, timeout=2)
            if devices:
                device = devices[0]
            else:
                _LOG.error("No devices found at IP address %s", address)
                return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

            device.auth()
            device.hello()

            _LOG.info("Broadlink device info: %s", devices)

            # if we are adding a new device: make sure it's not already configured
            if self._add_mode and self.config.contains(device.mac.hex()):
                _LOG.info(
                    "Skipping found device %s: already configured",
                    device.name,
                )
                return SetupError(IntegrationSetupError.OTHER)

            return BroadlinkConfig(
                identifier=device.mac.hex(),
                name=device.name,
                address=address,
                data={},
            )

        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("Setup Error: %s", err)
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)
