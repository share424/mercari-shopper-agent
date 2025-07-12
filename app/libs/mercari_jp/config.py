"""Mercari Configuration.

This module contains the configuration for the Mercari Shopping Agent.
"""

BROWSER_CONFIG = {
    # "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",  # noqa: E501
    # "viewport": ViewportSize(width=1366, height=768),
    "locale": "ja-JP",
    "timezone_id": "Asia/Tokyo",
    "geolocation": {"longitude": 139.6917, "latitude": 35.6895},  # Tokyo
    "permissions": ["geolocation"],
}
