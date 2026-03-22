"""1Control API client using Firebase authentication."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import aiohttp

from .const import (
    API_BASE_URL,
    BACKEND_API_KEY,
    FIREBASE_API_KEY,
    FIREBASE_AUTH_URL,
    FIREBASE_REFRESH_URL,
)

_LOGGER = logging.getLogger(__name__)


class OneControlAuthError(Exception):
    """Raised when authentication fails."""


class OneControlAPIError(Exception):
    """Raised when an API call fails."""


class OneControlAPI:
    """Client for the 1Control cloud API (webAdmin/v1)."""

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._id_token: str | None = None
        self._stored_refresh_token: str | None = None
        self._token_expiry: datetime | None = None
        self._uid: str | None = None

    @property
    def uid(self) -> str | None:
        return self._uid

    def _url(self, path: str) -> str:
        """Build a full API URL with the required backend API key."""
        return f"{API_BASE_URL}/{path}?key={BACKEND_API_KEY}"

    async def authenticate(self) -> str:
        """Sign in with email/password. Returns the Firebase UID."""
        payload = {
            "email": self._email,
            "password": self._password,
            "returnSecureToken": True,
        }
        try:
            async with self._session.post(
                f"{FIREBASE_AUTH_URL}?key={FIREBASE_API_KEY}",
                json=payload,
            ) as resp:
                if resp.status == 400:
                    raise OneControlAuthError("Invalid email or password")
                resp.raise_for_status()
                data = await resp.json()
        except aiohttp.ClientError as err:
            raise OneControlAPIError(f"Connection error during login: {err}") from err

        self._id_token = data["idToken"]
        self._stored_refresh_token = data["refreshToken"]
        self._uid = data["localId"]
        expires_in = int(data.get("expiresIn", 3600))
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
        _LOGGER.debug("Authenticated as uid=%s", self._uid)
        return self._uid

    async def _ensure_token(self) -> None:
        """Re-authenticate or refresh token if expired."""
        if self._id_token is None or (
            self._token_expiry and datetime.now() >= self._token_expiry
        ):
            if self._stored_refresh_token:
                await self._do_refresh()
            else:
                await self.authenticate()

    async def _do_refresh(self) -> None:
        """Refresh the Firebase ID token using the stored refresh token."""
        try:
            async with self._session.post(
                f"{FIREBASE_REFRESH_URL}?key={FIREBASE_API_KEY}",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._stored_refresh_token,
                },
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Token refresh failed, re-authenticating")
                    await self.authenticate()
                    return
                data = await resp.json()
        except aiohttp.ClientError:
            _LOGGER.warning("Connection error during token refresh, re-authenticating")
            await self.authenticate()
            return

        self._id_token = data["id_token"]
        self._stored_refresh_token = data["refresh_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._id_token}"}

    async def get_devices(self) -> list[dict]:
        """Return a flat list of controllable actions across all Solo devices.

        Each entry has:
          serial      – Solo device serial (int)
          link_serial – paired Link device serial (int)
          action      – action number on the Solo (int, 0-based)
          name        – friendly name of the action
          device_name – friendly name of the Solo device
        """
        await self._ensure_token()

        # 1. List Solo devices owned by this account
        try:
            async with self._session.get(
                self._url("devices/solo"),
                headers=self._auth_headers,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("GET devices/solo returned %s", resp.status)
                    return []
                data = await resp.json()
        except aiohttp.ClientError as err:
            raise OneControlAPIError(f"Failed to list devices: {err}") from err

        solos: list[dict] = data.get("items", []) if isinstance(data, dict) else []
        if not solos:
            return []

        devices: list[dict] = []
        for solo in solos:
            solo_serial = solo.get("serial")
            solo_name = solo.get("name") or f"1Control {solo_serial}"

            # 2. Find the Link device paired with this Solo
            link_serial = await self._get_link_serial(solo_serial)
            if link_serial is None:
                _LOGGER.warning(
                    "Solo %s has no paired Link device — cannot control remotely",
                    solo_serial,
                )
                continue

            # 3. Build one entry per configured action (cloned=True)
            actions = solo.get("actions", [])
            configured = [a for a in actions if a.get("cloned", False)]
            if not configured:
                _LOGGER.warning("Solo %s has no configured actions", solo_serial)
                continue

            for action in configured:
                action_number = action.get("number", 0)
                action_name = action.get("name") or f"Action {action_number}"
                devices.append(
                    {
                        "serial": solo_serial,
                        "link_serial": link_serial,
                        "action": action_number,
                        "name": action_name,
                        "device_name": solo_name,
                    }
                )

        return devices

    async def _get_link_serial(self, solo_serial: int) -> int | None:
        """Return the serial of the Link device paired with a Solo, or None."""
        try:
            async with self._session.get(
                self._url(f"device/{solo_serial}/link"),
                headers=self._auth_headers,
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("serial")
        except aiohttp.ClientError:
            return None

    async def trigger_device(
        self,
        solo_serial: int,
        link_serial: int,
        action: int = 0,
        open: bool = True,
    ) -> bool:
        """Trigger a device open or close via its paired Link. Returns True on success."""
        await self._ensure_token()
        payload = {
            "open": open,
            "serial": solo_serial,
            "action": action,
            "deviceType": "Solo",
        }
        try:
            async with self._session.post(
                self._url(f"link/{link_serial}/open"),
                json=payload,
                headers=self._auth_headers,
            ) as resp:
                success = resp.status in (200, 204)
                if not success:
                    body = await resp.text()
                    _LOGGER.error(
                        "Trigger device %s via link %s returned %s: %s",
                        solo_serial,
                        link_serial,
                        resp.status,
                        body[:200],
                    )
                return success
        except aiohttp.ClientError as err:
            raise OneControlAPIError(
                f"Failed to trigger device {solo_serial}: {err}"
            ) from err
