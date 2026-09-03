"""DataUpdateCoordinator for the Battery Emulator REST integration."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from datetime import datetime, timedelta
from typing import Awaitable, Callable, TypeVar

import aiohttp
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HOST,
    CONF_RESOLVED_IP,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DNS_TIMEOUT,
    DOMAIN,
    LAST_SUCCESSFUL_UPDATE,
    MAX_CHARGE_SPEED,
    MAX_DISCHARGE_SPEED,
    READ_RETRY_DELAYS,
    REQUEST_TIMEOUT,
    STALE_FAILURE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)
_ReadResultT = TypeVar("_ReadResultT")


class IncompleteSettingsResponse(Exception):
    """Error raised when a settings response is missing required values."""


def _normalize_base_url(host: str) -> URL:
    """Return a normalized HTTP URL for a hostname, IPv4, or IPv6 input."""
    value = host.strip().rstrip("/")
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        url = URL(value if "://" in value else f"http://{value}")
    else:
        url = URL.build(scheme="http", host=str(address))

    if url.scheme not in ("http", "https") or url.host is None:
        raise ValueError(
            "Host must be an HTTP(S) DNS hostname, IPv4 address, or IPv6 address"
        )
    return url


def _is_ip_address(host: str) -> bool:
    """Return whether host is a literal IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


async def _async_resolve_host(url: URL) -> str:
    """Resolve a configured URL host to one concrete IP address."""
    host = url.host
    if host is None:
        raise socket.gaierror("URL has no host")
    if _is_ip_address(host):
        return host

    async with asyncio.timeout(DNS_TIMEOUT):
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host,
            url.port or (443 if url.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    if not addresses:
        raise socket.gaierror(f"No addresses returned for {host}")
    return addresses[0][4][0]


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
        self._configured_url = _normalize_base_url(config_entry.data[CONF_HOST])
        self.host = str(self._configured_url).rstrip("/")
        self._resolved_ip: str | None = config_entry.data.get(CONF_RESOLVED_IP)
        self.device_name: str = "Battery Emulator"
        self._request_lock = asyncio.Lock()
        self._consecutive_failures = 0

    async def _async_request_target(
        self,
    ) -> tuple[str, dict[str, str], str | None]:
        """Select a concrete request URL while preserving HTTP and TLS hostnames."""
        configured_host = self._configured_url.host
        if configured_host is None or _is_ip_address(configured_host):
            return self.host, {}, None

        try:
            resolved_ip = await _async_resolve_host(self._configured_url)
        except (TimeoutError, socket.gaierror, OSError) as err:
            if self._resolved_ip is None:
                raise UpdateFailed(
                    f"DNS lookup failed for {configured_host} and no cached IP is available"
                ) from err
            resolved_ip = self._resolved_ip
            _LOGGER.warning(
                "DNS lookup failed for %s; using cached IP %s",
                configured_host,
                resolved_ip,
            )
        else:
            if resolved_ip != self._resolved_ip:
                self._resolved_ip = resolved_ip
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_RESOLVED_IP: resolved_ip,
                    },
                )

        request_url = str(self._configured_url.with_host(resolved_ip)).rstrip("/")
        server_hostname = (
            configured_host if self._configured_url.scheme == "https" else None
        )
        return request_url, {"Host": self._configured_url.raw_authority}, server_hostname

    async def _async_get_text(self, path: str) -> str:
        """Fetch one complete text response."""
        request_url, request_headers, server_hostname = (
            await self._async_request_target()
        )
        headers = {**request_headers, "Connection": "close"}
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with self.session.get(
                f"{request_url}{path}",
                headers=headers,
                server_hostname=server_hostname,
            ) as response:
                response.raise_for_status()
                return await response.text()

    async def _async_retry_read(
        self,
        description: str,
        operation: Callable[[], Awaitable[_ReadResultT]],
    ) -> _ReadResultT:
        """Retry an idempotent read after transient transport failures."""
        attempts = len(READ_RETRY_DELAYS) + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await operation()
            except aiohttp.ClientResponseError as err:
                raise UpdateFailed(
                    f"{description} returned HTTP {err.status}"
                ) from err
            except (
                TimeoutError,
                aiohttp.ClientError,
                IncompleteSettingsResponse,
                UpdateFailed,
            ) as err:
                last_error = err
                if attempt == attempts:
                    break
                _LOGGER.debug(
                    "%s attempt %d/%d failed with %s; retrying",
                    description,
                    attempt,
                    attempts,
                    self._describe_error(err),
                )
                await asyncio.sleep(READ_RETRY_DELAYS[attempt - 1])

        raise UpdateFailed(
            f"{description} failed after {attempts} attempts: "
            f"{self._describe_error(last_error)}"
        ) from last_error

    async def _async_read_settings(
        self,
    ) -> dict[str, float | datetime | None]:
        """Fetch and parse a complete settings response."""
        html = await self._async_get_text("/settings")
        max_charge = self._parse_float(
            html, r"Max charge speed:\s*([\d.]+)\s*A"
        )
        max_discharge = self._parse_float(
            html, r"Max discharge speed:\s*([\d.]+)\s*A"
        )
        if max_charge is None or max_discharge is None:
            raise IncompleteSettingsResponse(
                "response did not contain both charge and discharge limits"
            )
        return {
            MAX_CHARGE_SPEED: max_charge,
            MAX_DISCHARGE_SPEED: max_discharge,
            LAST_SUCCESSFUL_UPDATE: dt_util.utcnow(),
        }

    @staticmethod
    def _describe_error(error: Exception | None) -> str:
        """Return an error description that is useful even for blank timeouts."""
        if error is None:
            return "unknown error"
        detail = str(error).strip()
        return f"{type(error).__name__}: {detail}" if detail else type(error).__name__

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
            html = await self._async_retry_read(
                "Device information request",
                lambda: self._async_get_text(""),
            )
            match = re.search(r"Battery protocol:\s*([^<]+)", html)
            if match:
                self.device_name = match.group(1).strip()
        except UpdateFailed:
            _LOGGER.warning("Could not fetch device name from %s", self.host)

    async def _async_update_data(self) -> dict[str, float | datetime | None]:
        """Fetch data from the Battery Emulator REST API."""
        if self._request_lock.locked():
            _LOGGER.debug("Skipping update for %s because a request is already in progress", self.host)
            if self.data:
                return self.data
            raise UpdateFailed("Previous request still in progress")

        try:
            async with self._request_lock:
                data = await self._async_retry_read(
                    "Settings request",
                    self._async_read_settings,
                )
        except UpdateFailed as err:
            self._consecutive_failures += 1
            if self.data and self._consecutive_failures < STALE_FAILURE_LIMIT:
                log = _LOGGER.warning if self._consecutive_failures == 1 else _LOGGER.debug
                log(
                    "Battery Emulator update failed; retaining last data "
                    "(%d/%d failed cycles): %s",
                    self._consecutive_failures,
                    STALE_FAILURE_LIMIT,
                    err,
                )
                return self.data
            raise

        if self._consecutive_failures:
            _LOGGER.info(
                "Battery Emulator recovered after %d failed update cycle(s)",
                self._consecutive_failures,
            )
            self._consecutive_failures = 0
        return data

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
                request_url, request_headers, server_hostname = (
                    await self._async_request_target()
                )
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with self.session.get(
                        f"{request_url}/{endpoint}",
                        params={"value": str(value)},
                        headers={**request_headers, "Connection": "close"},
                        server_hostname=server_hostname,
                    ) as response:
                        response.raise_for_status()
        except (TimeoutError, aiohttp.ClientError, UpdateFailed) as err:
            raise UpdateFailed(
                f"Error sending update to {self.host}/{endpoint}: "
                f"{self._describe_error(err)}"
            ) from err
        await self.async_request_refresh()

    async def async_calibrate_soc(self) -> None:
        """Trigger a SOC calibration on the device."""
        try:
            async with self._request_lock:
                request_url, request_headers, server_hostname = (
                    await self._async_request_target()
                )
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with self.session.put(
                        f"{request_url}/calibrateSOC",
                        data="0",
                        headers={**request_headers, "Connection": "close"},
                        server_hostname=server_hostname,
                    ) as response:
                        response.raise_for_status()
        except (TimeoutError, aiohttp.ClientError, UpdateFailed) as err:
            raise UpdateFailed(
                f"Error calibrating SOC at {self.host}/calibrateSOC: "
                f"{self._describe_error(err)}"
            ) from err
        await self.async_request_refresh()
