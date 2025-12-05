"""
Configuration handling of the integration driver.

:copyright: (c) 2025 by Jack Powell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from dataclasses import dataclass

from ucapi_framework import BaseConfigManager


@dataclass
class BroadlinkConfig:
    """Broadlink device configuration."""

    identifier: str
    """Unique identifier of the device. (MAC Address)"""
    name: str
    """Friendly name of the device."""
    address: str
    """IP Address of device"""
    data: dict[str, dict[str, str]]
    """List of codes for the device, if any."""


class BroadlinkConfigManager(BaseConfigManager[BroadlinkConfig]):
    """Integration driver configuration class. Manages all configured Broadlink devices."""

    @property
    def data_path(self) -> str:
        """Return the configuration path."""
        return self._data_path

    def get_code(self, device_id: str, device_name: str, command: str) -> str | None:
        """Get a code for the given device and command."""

        device = self.get(device_id)
        if device is None:
            return None

        if hasattr(device, "data"):
            return device.data.get(device_name, {}).get(command)
        return None

    def append_code(
        self, device_id: str, device_name: str, command: str, code: str
    ) -> str:
        """Append new codes to the device configuration."""
        device = self.get(device_id)
        status = "Learned"
        if device is None:
            raise Exception(f"Device with ID {device_id} not found.")

        if hasattr(device, "data"):
            if command in device.data.get(device_name, {}):
                status = "Updated"
            if device_name not in device.data:
                device.data[device_name] = {}
            device.data[device_name][command] = code
        else:
            device.data.setdefault(device_name, {})[command] = code
        self.store()
        return status

    def remove_code(self, device_id: str, device_name: str, command: str) -> str:
        """Remove a code from the device configuration."""
        device = self.get(device_id)
        status = "Removed"
        if device is None:
            raise Exception(f"Device with ID {device_id} not found.")

        if command is None or command == "":
            device.data.pop(device_name, None)
        elif device_name in device.data:
            if command not in device.data[device_name]:
                status = "Nothing to remove"
            else:
                device.data[device_name].pop(command, None)
        else:
            status = "Device not found"

        self.store()
        return status
