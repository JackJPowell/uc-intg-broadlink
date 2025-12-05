"""Discover Broadlink devices in local network using SDDP protocol."""

import logging
from typing import Any

import broadlink
from ucapi_framework import DiscoveredDevice
from ucapi_framework.discovery import BaseDiscovery

_LOG = logging.getLogger(__name__)


class BroadlinkDiscovery(BaseDiscovery):
    """Discover Broadlink devices in local network using custom protocol."""

    async def discover(self) -> list[DiscoveredDevice]:
        """
        Parse Discovery responses and return a list of DiscoveredDevice.

        :return: List of DiscoveredDevice objects discovered in the local network.
        """

        devices = broadlink.discover(timeout=self.timeout)
        for device in devices:
            device.hello()
            parsed_device = self._parse_device(device)
            if parsed_device:
                self._discovered_devices.append(parsed_device)
        return self._discovered_devices

    def _parse_device(self, device: Any) -> DiscoveredDevice | None:
        """
        Parse a single device and return a DiscoveredDevice.

        :param device: The device to parse
        :return: DiscoveredDevice or None if parsing fails
        """
        return DiscoveredDevice(
            identifier=device.host[0],
            name=device.name,
            address=device.host[0],
            extra_data={},
        )
