"""
Configuration handling of the integration driver.

:copyright: (c) 2023-2024 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import dataclasses
import json
import logging
import os
from asyncio import Lock
from dataclasses import dataclass
from typing import Iterator
from ucapi import EntityTypes

_LOG = logging.getLogger(__name__)

_CFG_FILENAME = "config.json"


def create_entity_id(device_id: str, entity_type: EntityTypes) -> str:
    """Create a unique entity identifier for the given receiver and entity type."""
    if type(entity_type) is EntityTypes:
        entity_type_value = entity_type.value
    else:
        entity_type_value = str(entity_type)

    return f"{entity_type_value}.{device_id}"


def device_from_entity_id(entity_id: str) -> str | None:
    """
    Return the id prefix of an entity_id.

    :param entity_id: the entity identifier
    :return: the device prefix, or None if entity_id doesn't contain a dot
    """
    return entity_id.split(".", 1)[1]


@dataclass
class BroadlinkDevice:
    """Broadlink device configuration."""

    identifier: str
    """Unique identifier of the device. (MAC Address)"""
    name: str
    """Friendly name of the device."""
    address: str
    """IP Address of device"""
    data: dict[str, dict[str, str]]
    """List of codes for the device, if any."""


class _EnhancedJSONEncoder(json.JSONEncoder):
    """Python dataclass json encoder."""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class Devices:
    """Integration driver configuration class. Manages all configured Broadlink devices."""

    def __init__(self, data_path: str, add_handler, remove_handler):
        """
        Create a configuration instance for the given configuration path.

        :param data_path: configuration path for the configuration file and client certificates.
        """
        self._data_path: str = data_path
        self._cfg_file_path: str = os.path.join(data_path, _CFG_FILENAME)
        self._config: list[BroadlinkDevice] = []
        self._add_handler = add_handler
        self._remove_handler = remove_handler
        self.load()
        self._config_lock = Lock()

    @property
    def data_path(self) -> str:
        """Return the configuration path."""
        return self._data_path

    def all(self) -> Iterator[BroadlinkDevice]:
        """Get an iterator for all device configurations."""
        return iter(self._config)

    def contains(self, device_id: str) -> bool:
        """Check if there's a device with the given device identifier."""
        for item in self._config:
            if item.identifier == device_id:
                return True
        return False

    def add_or_update(self, device: BroadlinkDevice) -> None:
        """
        Add a new configured Broadlink device and persist configuration.

        The device is updated if it already exists in the configuration.
        """
        # duplicate check
        if not self.update(device):
            self._config.append(device)
            self.store()
            if self._add_handler is not None:
                self._add_handler(device)

    def get(self, device_id: str) -> BroadlinkDevice | None:
        """Get device configuration for given identifier."""
        for item in self._config:
            if item.identifier == device_id:
                # return a copy
                return dataclasses.replace(item)
        return None

    def update(self, device: BroadlinkDevice) -> bool:
        """Update a configured Broadlink device and persist configuration."""
        for item in self._config:
            if item.identifier == device.identifier:
                item.address = device.address
                item.name = device.name
                item.data = device.data
                return self.store()
        return False

    def get_code(self, device_id: str, device_name: str, command: str) -> str | None:
        """Get a code for the given device and command."""
        code = None
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

    def remove(self, device_id: str) -> bool:
        """Remove the given device configuration."""
        device = self.get(device_id)
        if device is None:
            return False
        try:
            self._config.remove(device)
            if self._remove_handler is not None:
                self._remove_handler(device)
            return True
        except ValueError:
            pass
        return False

    def clear(self) -> None:
        """Remove the configuration file."""
        self._config = []

        if os.path.exists(self._cfg_file_path):
            os.remove(self._cfg_file_path)

        if self._remove_handler is not None:
            self._remove_handler(None)

    def store(self) -> bool:
        """
        Store the configuration file.

        :return: True if the configuration could be saved.
        """
        try:
            with open(self._cfg_file_path, "w+", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, cls=_EnhancedJSONEncoder)
            return True
        except OSError as err:
            _LOG.error("Cannot write the config file: %s", err)

        return False

    def load(self) -> bool:
        """
        Load the config into the config global variable.

        :return: True if the configuration could be loaded.
        """
        try:
            with open(self._cfg_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                # not using BroadlinkDevice(**item) to be able to migrate
                # old configuration files with missing attributes
                device = BroadlinkDevice(
                    item.get("identifier"),
                    item.get("name", ""),
                    item.get("address"),
                    item.get("data", {}),
                )
                self._config.append(device)
            return True
        except OSError as err:
            _LOG.error("Cannot open the config file: %s", err)
        except (AttributeError, ValueError, TypeError) as err:
            _LOG.error("Empty or invalid config file: %s", err)

        return False

    def migration_required(self) -> bool:
        """Check if configuration migration is required."""
        return False

    async def migrate(self) -> bool:
        """Migrate configuration if required."""
        return True


devices: Devices | None = None
