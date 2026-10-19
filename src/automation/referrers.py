"""Social and messaging platform referrer simulator for realistic referral visits.

Simulates genuine inbound traffic originating from major social and messaging
platforms: Instagram, Telegram, Facebook, YouTube, Twitter/X, and Reddit.
Provides authentic HTTP Referer headers and URL link-shim redirects.
"""

import random
import string
import urllib.parse
from typing import Dict, List, Optional


def _rand_slug(length: int = 10) -> str:
    """Generate a random alphanumeric slug for link shims."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


# ── Referral Platform Pools ──────────────────────────────────
REFERRER_POOLS: Dict[str, Dict[str, any]] = {
    "instagram": {
        "name": "Instagram",
        "domain": "instagram.com",
        "weight": 30,
        "templates": [
            "https://l.instagram.com/?u={encoded_url}",
            "https://www.instagram.com/",
            "https://l.instagram.com/",
            "https://www.instagram.com/p/{slug}/",
        ],
    },
    "telegram": {
        "name": "Telegram",
        "domain": "telegram.org",
        "weight": 25,
        "templates": [
            "https://t.me/",
            "https://web.telegram.org/a/",
            "https://web.telegram.org/k/",
            "https://t.me/s/{channel}",
            "https://t.me/share/url?url={encoded_url}",
        ],
    },
    "facebook": {
        "name": "Facebook",
        "domain": "facebook.com",
        "weight": 20,
        "templates": [
            "https://l.facebook.com/l.php?u={encoded_url}&h={slug}",
            "https://www.facebook.com/",
            "https://m.facebook.com/",
            "https://lm.facebook.com/l.php?u={encoded_url}",
        ],
    },
    "youtube": {
        "name": "YouTube",
        "domain": "youtube.com",
        "weight": 15,
        "templates": [
            "https://www.youtube.com/redirect?q={encoded_url}&redir_token={slug}",
            "https://www.youtube.com/",
            "https://m.youtube.com/",
            "https://youtu.be/{slug}",
        ],
    },
    "twitter": {
        "name": "X (Twitter)",
        "domain": "x.com",
        "weight": 5,
        "templates": [
            "https://t.co/{slug}",
            "https://x.com/",
            "https://twitter.com/",
        ],
    },
    "reddit": {
        "name": "Reddit",
        "domain": "reddit.com",
        "weight": 5,
        "templates": [
            "https://out.reddit.com/",
            "https://www.reddit.com/r/technology/",
            "https://www.reddit.com/r/webdev/",
            "https://www.reddit.com/r/freebies/",
        ],
    },
}

_TELEGRAM_CHANNELS = [
    "tech_deals",
    "cloud_tools",
    "web_resources",
    "free_storage",
    "app_recommendations",
    "dev_tools",
]


def get_random_referrer(target_url: str = "", preferred_platform: Optional[str] = None) -> Dict[str, str]:
    """Select a realistic referrer URL simulating organic social referral traffic.

    Args:
        target_url: The destination referral link (e.g. TenBox referral URL).
        preferred_platform: Optional platform key ('instagram', 'telegram', 'facebook', 'youtube').

    Returns:
        Dict with keys: 'platform', 'url', 'domain'.
    """
    if preferred_platform and preferred_platform.lower() in REFERRER_POOLS:
        platform_key = preferred_platform.lower()
    else:
        keys = list(REFERRER_POOLS.keys())
        weights = [REFERRER_POOLS[k]["weight"] for k in keys]
        platform_key = random.choices(keys, weights=weights, k=1)[0]

    platform_data = REFERRER_POOLS[platform_key]
    template = random.choice(platform_data["templates"])

    encoded_url = urllib.parse.quote(target_url, safe="") if target_url else "https://websurfer.1024tenbox.com"
    slug = _rand_slug(random.randint(8, 14))
    channel = random.choice(_TELEGRAM_CHANNELS)

    referrer_url = template.format(
        encoded_url=encoded_url,
        slug=slug,
        channel=channel,
    )

    return {
        "key": platform_key,
        "platform": platform_data["name"],
        "url": referrer_url,
        "domain": platform_data["domain"],
    }


def get_all_platforms() -> List[str]:
    """List of all available referrer platform keys."""
    return list(REFERRER_POOLS.keys())
