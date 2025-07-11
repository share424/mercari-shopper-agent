"""Mercari Configuration.

This module contains the configuration for the Mercari Shopping Agent.
"""

from playwright.async_api import ViewportSize

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"  # noqa: E501
VIEWPORT = ViewportSize(width=390, height=844)
