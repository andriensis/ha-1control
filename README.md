# 1Control for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

> **Disclaimer:** This is an unofficial, community-made integration and is not affiliated with, endorsed by, or supported by 1Control. Use at your own risk.
>
> This integration was vibe coded with [Claude](https://claude.ai) — it works, but treat it accordingly.

A Home Assistant custom integration for controlling **1Control Solo** gates and doors via the 1Control cloud (Link2 bridge required).

## Features

- Automatically discovers all gates/doors linked to your 1Control account
- Each configured action appears as a **Cover** entity (device class: Gate)
- Supports open and close commands

## Requirements

- A [1Control](https://www.1control.it) account with at least one **Solo** device
- A **Link2** bridge paired to the Solo (required for remote/cloud control)
- Home Assistant 2024.1 or later

## Installation

### Via HACS (recommended)

1. In HACS, open the 3-dot menu → **Custom repositories**
2. Add this repository URL with category **Integration**
3. Click **Download**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/onecontrol/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **1Control**
3. Enter your 1Control account email and password
4. Select which gates/doors to add — each configured action on a Solo appears as a separate entity

## Entities

| Entity type | Device class | Supported features |
|-------------|-------------|-------------------|
| Cover | Garage | Open, Close |

State is tracked **optimistically**: after an open command the entity reports open, then automatically reverts to closed after 15 seconds to mirror the gate's physical auto-close behaviour. There is no real-time state feedback from the cloud API.

## Troubleshooting

- **"No devices found"** — ensure your Solo has at least one configured action (cloned action) in the 1Control app, and that a Link2 bridge is paired to it.
- **"Invalid auth"** — double-check your 1Control app email and password.
- **Gate triggered but HA shows error** — check the HA logs (`Settings → System → Logs`) for details from the `onecontrol` component.

## Contributing

Pull requests are welcome. Please open an issue first for significant changes.

## License

MIT
