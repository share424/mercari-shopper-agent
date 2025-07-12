"""Mercari Configuration.

This module contains the configuration for the Mercari Shopping Agent.
"""

from playwright.async_api import ViewportSize

BROWSER_CONFIG = {
    "user_agent": "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",  # noqa: E501
    "viewport": ViewportSize(width=360, height=740),
    "locale": "ja-JP",
    "timezone_id": "Asia/Tokyo",
    "geolocation": {"longitude": 139.6917, "latitude": 35.6895},  # Tokyo
    "permissions": ["geolocation"],
}
