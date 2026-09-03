"""Config flow for the Battery Emulator REST integration."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_RESOLVED_IP,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REQUEST_TIMEOUT,
)
from .coordinator import _async_resolve_host, _is_ip_address, _normalize_base_url

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
    }
)


async def _validate_connection(hass: HomeAssistant, host: str) -> dict[str, str]:
    """Validate the address and return device details."""
    try:
        configured_url = _normalize_base_url(host)
        resolved_ip = await _async_resolve_host(configured_url)
    except (TimeoutError, OSError, ValueError) as err:
        raise CannotConnect from err

    request_url = str(configured_url.with_host(resolved_ip)).rstrip("/")
    configured_host = configured_url.host or ""
    request_headers = (
        {} if _is_ip_address(configured_host) else {"Host": configured_url.raw_authority}
    )
    server_hostname = (
        configured_host
        if configured_url.scheme == "https" and not _is_ip_address(configured_host)
        else None
    )

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            response = await async_get_clientsession(hass).get(
                request_url,
                headers=request_headers,
                server_hostname=server_hostname,
            )
            response.raise_for_status()
            html = await response.text()
    except (TimeoutError, aiohttp.ClientError) as err:
        raise CannotConnect from err

    match = re.search(r"Battery protocol:\s*([^<]+)", html)
    return {
        "device_name": match.group(1).strip() if match else "Battery Emulator",
        "resolved_ip": resolved_ip,
    }


class BatteryEmulatorRestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Emulator REST."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BatteryEmulatorRestOptionsFlow:
        """Get the options flow for this handler."""
        return BatteryEmulatorRestOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                info = await _validate_connection(self.hass, host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                normalized_host = str(_normalize_base_url(host)).rstrip("/")
                configured_host = _normalize_base_url(normalized_host).host or ""
                return self.async_create_entry(
                    title=info["device_name"],
                    data={
                        **user_input,
                        CONF_HOST: normalized_host,
                        **(
                            {CONF_RESOLVED_IP: info["resolved_ip"]}
                            if not _is_ip_address(configured_host)
                            else {}
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the Battery Emulator address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                info = await _validate_connection(self.hass, host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                normalized_host = str(_normalize_base_url(host)).rstrip("/")
                configured_host = _normalize_base_url(normalized_host).host or ""
                data = {**entry.data, CONF_HOST: normalized_host}
                if _is_ip_address(configured_host):
                    data.pop(CONF_RESOLVED_IP, None)
                else:
                    data[CONF_RESOLVED_IP] = info["resolved_ip"]

                return self.async_update_reload_and_abort(
                    entry,
                    title=info["device_name"],
                    data=data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=errors,
        )


class BatteryEmulatorRestOptionsFlow(OptionsFlow):
    """Handle options for Battery Emulator REST."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            self.config_entry.data.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                        ),
                    ): vol.All(int, vol.Range(min=10, max=3600)),
                }
            ),
        )


class CannotConnect(Exception):
    """Error raised when the Battery Emulator cannot be reached."""
