"""
This module implements a Remote Two/3 integration driver for Broadlink devices.

:copyright: (c) 2025 Jack Powell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os

from discover import BroadlinkDiscovery
from ir_emitter import BroadlinkIREmitter
from media_player import BroadlinkMediaPlayer
from remote import BroadlinkRemote
from rm import Broadlink
from setup import BroadlinkSetupFlow
from ucapi_framework import BaseIntegrationDriver, get_config_path

from config_manager import BroadlinkConfig, BroadlinkConfigManager


async def main():
    """Start the Remote Two integration driver."""
    logging.basicConfig()

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("rm").setLevel(level)
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("config").setLevel(level)
    logging.getLogger("discover").setLevel(level)
    logging.getLogger("setup").setLevel(level)

    driver = BaseIntegrationDriver(
        device_class=Broadlink,
        entity_classes=[
            BroadlinkMediaPlayer,
            BroadlinkRemote,
            lambda cfg, dev: BroadlinkIREmitter(cfg, dev),
        ],
        driver_id="broadlink_driver",
        require_connection_before_registry=True,
    )
    driver.config_manager = BroadlinkConfigManager(
        get_config_path(driver.api.config_dir_path),
        driver.on_device_added,
        driver.on_device_removed,
        config_class=BroadlinkConfig,
    )

    await driver.register_all_device_instances()

    discovery = BroadlinkDiscovery(timeout=1)
    setup_handler = BroadlinkSetupFlow.create_handler(driver, discovery=discovery)
    await driver.api.init("driver.json", setup_handler)

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
