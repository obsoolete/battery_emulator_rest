"""DataUpdateCoordinator for the Battery Emulator REST integration."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from time import monotonic

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LAST_SUCCESSFUL_UPDATE,
    MAX_CHARGE_SPEED,
    MAX_DISCHARGE_SPEED,
)

_LOGGER = logging.getLogger(__name__)


class BatteryEmulatorCoordinator(DataUpdateCoordinator[dict[str, float | datetime | None]]):
    """Coordinator to fetch data from the Battery Emulator REST API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        host = config_entry.data[CONF_HOST].rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"
        self.host: str = host
        self.device_name: str = "Battery Emulator"
        self._request_lock = asyncio.Lock()
        self._backoff_until_monotonic = 0.0
        self._failure_backoff_seconds = max(10, int(self.update_interval.total_seconds()))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the Battery Emulator."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.device_name,
            manufacturer="Battery Emulator",
            configuration_url=self.host,
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        self.session = async_get_clientsession(self.hass)

        # Scrape device name from the root page.
        try:
            async with asyncio.timeout(10):
                resp = await self.session.get(self.host)
                resp.raise_for_status()
                html = await resp.text()
            match = re.search(r"Battery protocol:\s*([^<]+)", html)
            if match:
                self.device_name = match.group(1).strip()
        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.warning("Could not fetch device name from %s", self.host)

    async def _async_update_data(self) -> dict[str, float | datetime | None]:
        """Fetch data from the Battery Emulator REST API."""
        if self._request_lock.locked():
            _LOGGER.debug("Skipping update for %s because a request is already in progress", self.host)
            if self.data:
                return self.data
            raise UpdateFailed("Previous request still in progress")

        if monotonic() < self._backoff_until_monotonic:
            _LOGGER.debug("Skipping update for %s during failure backoff window", self.host)
            if self.data:
                return self.data
            raise UpdateFailed("Waiting before retrying after previous failure")

        try:
            async with self._request_lock:
                async with asyncio.timeout(10):
                    resp = await self.session.get(f"{self.host}/settings")
                    resp.raise_for_status()
                    html = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            self._backoff_until_monotonic = monotonic() + self._failure_backoff_seconds
            raise UpdateFailed(f"Error fetching data from {self.host}/settings: {err}") from err

        self._backoff_until_monotonic = 0.0

        return {
            MAX_CHARGE_SPEED: self._parse_float(html, r"Max charge speed:\s*([\d.]+)\s*A"),
            MAX_DISCHARGE_SPEED: self._parse_float(html, r"Max discharge speed:\s*([\d.]+)\s*A"),
            LAST_SUCCESSFUL_UPDATE: dt_util.utcnow(),
        }

    @staticmethod
    def _parse_float(html: str, pattern: str) -> float | None:
        """Extract a float value from HTML using a regex pattern."""
        match = re.search(pattern, html)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    async def async_set_max_charge(self, value: float) -> None:
        """Set the max charge speed on the device."""
        await self._async_send_update("updateMaxChargeA", value)

    async def async_set_max_discharge(self, value: float) -> None:
        """Set the max discharge speed on the device."""
        await self._async_send_update("updateMaxDischargeA", value)

    async def _async_send_update(self, endpoint: str, value: float) -> None:
        """Send a value update to the device and refresh data."""
        try:
            async with self._request_lock:
                async with asyncio.timeout(10):
                    resp = await self.session.get(
                        f"{self.host}/{endpoint}", params={"value": str(value)}
                    )
                    resp.raise_for_status()
        except (TimeoutError, aiohttp.ClientError) as err:
            self._backoff_until_monotonic = monotonic() + self._failure_backoff_seconds
            raise UpdateFailed(
                f"Error sending update to {self.host}/{endpoint}: {err}"
            ) from err
        self._backoff_until_monotonic = 0.0
        await self.async_request_refresh()

    async def async_calibrate_soc(self) -> None:
        """Trigger a SOC calibration on the device."""
        try:
            async with self._request_lock:
                async with asyncio.timeout(10):
                    resp = await self.session.put(
                        f"{self.host}/calibrateSOC", data="0"
                    )
                    resp.raise_for_status()
        except (TimeoutError, aiohttp.ClientError) as err:
            self._backoff_until_monotonic = monotonic() + self._failure_backoff_seconds
            raise UpdateFailed(
                f"Error calibrating SOC at {self.host}/calibrateSOC: {err}"
            ) from err
        self._backoff_until_monotonic = 0.0
        await self.async_request_refresh()
