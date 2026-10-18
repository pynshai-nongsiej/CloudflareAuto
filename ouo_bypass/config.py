"""Configuration for OUO.io Link Bypass Automation."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Path to the links file (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LINKS_FILE = str(PROJECT_ROOT / "ouolinks.txt")

# OUO.io-specific selectors and patterns
OUO_FORM_ID = "#form-go"
OUO_SUBMIT_SELECTORS = [
    "#form-go button[type='submit']",
    "#form-go input[type='submit']",
    "#btn-main",
    "button.btn-primary",
    "a.btn.btn-primary",
    "#btn-go",
]

# Cloudflare / captcha challenge selectors
CHALLENGE_SELECTORS = [
    "iframe[src*='challenges.cloudflare.com']",
    "#turnstile-wrapper iframe",
    ".cf-turnstile iframe",
    "iframe[title*='Cloudflare']",
]

# Known ouo.io domains
OUO_DOMAINS = ["ouo.io", "ouo.press"]


@dataclass
class OUOConfig:
    """Runtime configuration for the OUO bypass bot."""
    links_file: str = DEFAULT_LINKS_FILE
    headless: bool = True
    headed: bool = False  # CLI override
    # Timing
    page_load_timeout: int = 60  # seconds to wait for page load
    form_wait_timeout: int = 30  # seconds to wait for form to appear
    challenge_wait_timeout: int = 45  # seconds to wait for Cloudflare/captcha
    countdown_wait: int = 15  # max seconds to wait for countdown timer
    # Delays between actions (human-like)
    action_delay_min: float = 1.5
    action_delay_max: float = 4.0
    # Delays between links
    link_delay_min: float = 15.0
    link_delay_max: float = 45.0
    # Dwell time on final destination (minimum 7 seconds as requested)
    destination_dwell_min: float = 7.0
    destination_dwell_max: float = 15.0
    # Scroll settings
    scroll_steps: int = 4
    # Screenshots
    screenshot_dir: str = "screenshots"
    take_screenshots: bool = True
    # Logging
    log_level: str = "INFO"
