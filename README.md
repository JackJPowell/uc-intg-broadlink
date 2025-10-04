[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Release](https://img.shields.io/github/v/release/jackjpowell/uc-intg-broadlink)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/jackjpowell/uc-intg-broadlink/total)
<a href="#"><img src="https://img.shields.io/maintenance/yes/2025.svg"></a>
[![Buy Me A Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee&nbsp;☕-FFDD00?logo=buy-me-a-coffee&logoColor=white&labelColor=grey)](https://buymeacoffee.com/jackpowell)

# Broadlink integration for Remote Two/3

This integration is based on the [broadlink](https://github.com/mjg59/python-broadlink) library and uses the
[uc-integration-api](https://github.com/aitatoi/integration-python-library) to communicate with the Remote Two/3.

Entities:
- [Remote](https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_remote.md)
- [Media Player](https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_media_player.md)
- [IR Emitter](https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_ir_emitter.md)

Supported devices:
- Broadlink devices such as the RM4 Pro

Supported attributes:
- State (on, off, unknown)

Supported commands:
- Send Command
- Send IR

# Getting Started

There are two ways to get started

## Option 1
1. Use an Unfolded Circle Dock to define a custom code set and learn your IR commands. This will create IR entities that you can reference in your activities. This is the preferred way to get started.
   <img width="1514" height="486" alt="CleanShot 2025-08-22 at 16 53 26" src="https://github.com/user-attachments/assets/5f858d3c-1d3a-49fc-9819-d12ae79fbe58" />

If you go with `option 1`, you will follow the standard IR learning process for the Unfolded Circle Dock. During this process, select your broadlink device as the Infrared output device. Continue by including IR entity in your activity and finish by mapping it to your buttons. 

### Supported formats for Option 1:
- Pronto
- HEX (NEC Protocol)
- Global Cache (Untested)

When you use your dock to learn a new IR command, it will be represented in the following format: `<protocol>;<hex-ir-code>;<bits>;<repeat-count>` E.g. `3;0x1FEF807;32;0` Each protocol needs to be translated for your broadlink device and presently only the NEC protocol is supported and is represented by a 3 at the start of the custom command. 

 
## Option 2

## How to Use the custom learning and sending commands

There are three main modes when interacting with the integration: Learning, Deleting and Sending commmands. Start by including the remote and media player in an activity. Then place a media player in the bottom third of the screen. It should be at least 3 rows tall. All commands referenced below are case insensitive. I've made everything uppercase for clarity, but it's not required. This means that you can't have devices or commands that are only differentiated by case.

<img height="250" alt="CleanShot 2025-08-18 at 15 30 25" src="https://github.com/user-attachments/assets/b05448e9-bb38-49a4-a6dd-e25997e37361" />

### Learning

Let's start by learning a new command.
1. Place a new button on the screen and select `Send Command`.
2. `Command` will take a set of options separated by `:`.
    1. `MODE`:`FREQUENCY_TYPE`:`DEVICE`:`COMMAND`  e.g. `LEARN:RF:FAN:ON` or `LEARN:IR:RECEIVER:TOGGLE`
    2. Once clicked, the media player you placed on the screen will walk you through the learning process. (Must be done on device)
    3. Specifically for RF, you can optionally include the frequency at the end of the command and skip the frequency scanning process. `LEARN:RF:FAN:ON:332.0`
4. Once learned, the included media player entity will update its `source list` with your new command.

https://github.com/user-attachments/assets/aa6e8d70-9d75-4ca8-8861-e6242c4c4fb9

### Supported formats for Option 1:
- Full IR support - Broadlink device dependent
- RF 310Mhz - 433Mhz

### Sending

There are two ways to send a command: Using the Media Player Source List or with the Remote Entity's `Send Command` option.

1. The included media player entity will update its `source list` will your new command.
2. Include a new button tied to the media player and select `Input Source` then pick your command from the list.
3. You can also use the remote entity's `Send Command` option: `SEND`:`DEVICE`:`COMMAND` e.g. `SEND:FAN:ON`
  3.1 For sending, you can also exclude the `SEND` keyword. e.g. `FAN:ON` 

### Deleting

Command cleanup follows a similiar pattern to learning.
1. Place a new button on the screen and select `Send Command`.
2. `Command` will take a set of separated by `:`.
  2.1. `MODE`:`DEVICE`:`COMMAND`  e.g. `DELETE:FAN:ON` or `REMOVE:RECEIVER`
    2.1.1 `COMMAND` is optional. If not supplied, the entire `DEVICE` will be removed
  2.2. Notice the multiple examples. You can use the `DELETE` or `REMOVE` keyword and you can remove individual commands or entire devices

## Network

- The Broadlink device must be on the same network subnet as the Remote. 
- When using DHCP: a static IP address reservation for the Broadlink device(s) is recommended.

## Broadlink device

- A Broadlink that is network enabled is required to use the integration. Please refer to the broadlink documentation for additional information on supported models. 

## Usage

### Docker
```
docker run -d \
  --name broadlink \
  --network host \
  -v $(pwd)/<local_directory>:/config \
  --restart unless-stopped \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  ghcr.io/jackjpowell/uc-intg-broadlink:latest
```

### Docker Compose

```
  broadlink:
    container_name: broadlink
    image: ghcr.io/jackjpowell/uc-intg-broadlink:latest
    network_mode: host
    volumes:
      - ./<local_directory>:/config
    environment:
      - UC_INTEGRATION_HTTP_PORT=9090
    restart: unless-stopped
```

### Install on Remote

- Download tar.gz file from Releases section of this repository
- Upload the file to the remove via the integrations tab (Requires Remote Beta)

### Setup (For Development)

- Requires Python 3.11
- Install required libraries:  
  (using a [virtual environment](https://docs.python.org/3/library/venv.html) is highly recommended)
```shell
pip3 install -r requirements.txt
```

For running a separate integration driver on your network for Remote Two/3, the configuration in file
[driver.json](driver.json) needs to be changed:

- Change `name` to easily identify the driver for discovery & setup  with Remote Two/3 or the web-configurator.
- Optionally add a `"port": 8090` field for the WebSocket server listening port.
    - Default port: `9090`
    - This is also overrideable with environment variable `UC_INTEGRATION_HTTP_PORT`

### Run

```shell
UC_CONFIG_HOME=./ python3 intg-broadlink/driver.py
```

See available [environment variables](https://github.com/unfoldedcircle/integration-python-library#environment-variables)
in the Python integration library to control certain runtime features like listening interface and configuration directory.

The configuration file is loaded & saved from the path specified in the environment variable `UC_CONFIG_HOME`.
Otherwise, the `HOME` path is used or the working directory as fallback.

The client name prefix used for pairing can be set in ENV variable `UC_CLIENT_NAME`. The hostname is used by default.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the
[tags and releases in this repository](https://github.com/jackjpowell/uc-intg-broadlink/releases).

## Changelog

The major changes found in each new release are listed in the [changelog](CHANGELOG.md)
and under the GitHub [releases](https://github.com/jackjpowell/uc-intg-broadlink/releases).

## Contributions

Please read the [contribution guidelines](CONTRIBUTING.md) before opening a pull request.

## License

This project is licensed under the [**Mozilla Public License 2.0**](https://choosealicense.com/licenses/mpl-2.0/).
See the [LICENSE](LICENSE) file for details.
