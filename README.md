# 1Control for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

> **Disclaimer:** This is an unofficial, community-made integration and is not affiliated with, endorsed by, or supported by 1Control. Use at your own risk.
>
> This integration was vibe coded with [Claude](https://claude.ai) — it works, but treat it accordingly.

A Home Assistant custom integration for controlling **1Control Solo** gates and doors via the 1Control cloud (Link bridge required).

## Features

- Automatically discovers all gates/doors linked to your 1Control account
- Each configured action appears as a **Cover** entity (device class: Gate)
- Supports open and close commands

## Requirements

- A 1Control web account (see below)
- A **Solo** device added to your web account
- A **Link** bridge paired to the Solo (required for remote/cloud control)
- Home Assistant 2024.1 or later

## Setting up a 1Control web account

If you already have the 1Control dashboard set up and linked to your Solo device you can skip this step.

1. Create an account at [web.1control.eu](https://web.1control.eu/)
2. Make a note of your email and password — you will need them during integration setup
3. Once the account is created, go to the [dashboard](https://web.1control.eu/web/en/#/dashboard)
4. Click **Add** in the "Add device" section and select **Solo device**
5. Follow the on-screen guide to add a web user to your Solo device

> **Note:** You need to be physically close to your 1Control Solo during this setup step.

## Installation

### Via HACS (recommended)

> **Prerequisites:** You need [HACS](https://hacs.xyz/) installed in your Home Assistant. If you don't have it yet, follow the [HACS installation guide](https://hacs.xyz/docs/use/download/download/) first.

**Step 1 — Add the repository to HACS:**

[![Add Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andriensis&repository=ha-1control&category=integration)

Click the button above to add the repository. This opens HACS in your Home Assistant and adds the 1Control repository. If the button doesn't work, add it manually:

1. Open **HACS** > **Integrations** > click the **three-dot menu** (top right) > **Custom repositories**
2. Paste `https://github.com/andriensis/ha-1control/` as the URL
3. Select **Integration** as the category and click **Add**

**Step 2 — Download the integration:**

1. In HACS, find **1Control** in the integration list (search if needed)
2. Click on it, then click **Download** (bottom right)
3. Select the latest version and confirm
4. **Restart Home Assistant**

**Step 3 — Add the integration to Home Assistant:**

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=onecontrol)

Click the button above to start the setup, or go to **Settings > Devices & Services > + Add Integration** and search for **1Control**.

### Manual

1. Copy the `custom_components/onecontrol/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **1Control**
3. Enter your 1Control account email and password
4. Select which gates/doors to add — each configured action on a Solo appears as a separate entity

## Screenshots

| Login | Select devices |
|-------|---------------|
| ![Login](docs/login.png) | ![Select devices](docs/select-devices.png) |

| Integration | Gate entity |
|-------------|------------|
| ![Integration](docs/integration.png) | ![Gate](docs/gate.png) |

## Entities

| Entity type | Device class | Supported features |
|-------------|-------------|-------------------|
| Cover | Garage | Open, Close |

State is tracked **optimistically**: after an open command the entity reports open, then automatically reverts to closed after 10 seconds to mirror the gate's physical auto-close behaviour. There is no real-time state feedback from the cloud API.

## Architecture & credentials

```
Home Assistant
      │
      │  email + password (stored in HA config entry)
      ▼
1Control Firebase Auth  ──►  short-lived ID token (1 hour, auto-refreshed)
      │
      │  Bearer token + API key
      ▼
1Control Cloud API (onecontrolcloud.appspot.com)
      │
      │  trigger command
      ▼
   Link bridge  ──►  Solo device  ──►  gate/door
```

**Your credentials are never sent anywhere except 1Control's own servers.** The email and password you enter are used solely to obtain a Firebase ID token from 1Control's authentication service — the same call the official mobile app makes. The token is short-lived and automatically refreshed; your password is only used again if the refresh token expires. No credentials are logged or transmitted to any third party.

## Troubleshooting

- **"No devices found"** — ensure your Solo has at least one configured action (cloned action) in the 1Control app, and that a Link bridge is paired to it.
- **"Invalid auth"** — double-check your 1Control app email and password.
- **Gate triggered but HA shows error** — check the HA logs (`Settings → System → Logs`) for details from the `onecontrol` component.

## Contributing

Pull requests are welcome. Please open an issue first for significant changes.

## License

MIT
