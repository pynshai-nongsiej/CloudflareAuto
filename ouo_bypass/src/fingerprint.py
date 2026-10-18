"""Browser fingerprinting and stealth — reuses patterns from the blog_ad_automation module."""

import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ─── Realistic User Agent Database ─────────────────────────────────────────────

_UA_DATABASE: List[Dict[str, str]] = [
    # Chrome on Windows
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    # Chrome on macOS
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    # Chrome on Linux
    {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "platform": "linux", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36", "platform": "linux", "browser": "chrome"},
    # Edge on Windows
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0", "platform": "win32", "browser": "edge"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0", "platform": "win32", "browser": "edge"},
]

# ─── GPU / WebGL Profiles ───────────────────────────────────────────────────────

_GPU_PROFILES = [
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1"},
    {"vendor": "Apple Inc.", "renderer": "Apple M2"},
    {"vendor": "Apple Inc.", "renderer": "Apple M3"},
    {"vendor": "Intel Inc.", "renderer": "Intel(R) Iris(TM) Plus Graphics 640"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)"},
]

# ─── Timezone pools ──────────────────────────────────────────────────────────────

_TIMEZONES = [
    {"tz": "America/New_York", "locale": "en-US", "offset": -300},
    {"tz": "America/Chicago", "locale": "en-US", "offset": -360},
    {"tz": "America/Los_Angeles", "locale": "en-US", "offset": -480},
    {"tz": "America/Denver", "locale": "en-US", "offset": -420},
    {"tz": "America/Phoenix", "locale": "en-US", "offset": -420},
    {"tz": "America/Detroit", "locale": "en-US", "offset": -300},
    {"tz": "America/Indiana/Indianapolis", "locale": "en-US", "offset": -300},
]

_LANGUAGE_SETS = [
    ["en-US", "en"],
]


_VIEWPORT_PRESETS = [
    (1366, 768), (1440, 900), (1536, 864), (1920, 1080),
    (1280, 800), (1600, 900), (1280, 720),
]


@dataclass
class BrowserFingerprint:
    user_agent: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    hardware_concurrency: int
    device_memory: int
    platform: str
    languages: List[str]
    timezone: str
    timezone_offset: int
    locale: str
    webgl_vendor: str
    webgl_renderer: str
    color_depth: int
    max_touch_points: int


def generate_fingerprint(prefer_platform: Optional[str] = None) -> BrowserFingerprint:
    """Generate a realistic randomized browser profile."""
    if prefer_platform:
        filtered = [e for e in _UA_DATABASE if e["platform"] == prefer_platform]
        pool = filtered if filtered else _UA_DATABASE
    else:
        pool = _UA_DATABASE

    entry = random.choice(pool)
    ua = entry["ua"]

    if "Macintosh" in ua:
        nav_platform = "MacIntel"
        gpu_pool = [p for p in _GPU_PROFILES if "Apple" in p["vendor"] or "Intel" in p["vendor"]]
        scale = 2.0
    elif "Linux" in ua:
        nav_platform = "Linux x86_64"
        gpu_pool = _GPU_PROFILES
        scale = 1.0
    else:
        nav_platform = "Win32"
        gpu_pool = [p for p in _GPU_PROFILES if "Google" in p["vendor"]]
        scale = 1.0

    gpu = random.choice(gpu_pool)
    base_w, base_h = random.choice(_VIEWPORT_PRESETS)
    tz_entry = random.choice(_TIMEZONES)
    lang_set = random.choice(_LANGUAGE_SETS)

    return BrowserFingerprint(
        user_agent=ua,
        viewport_width=base_w,
        viewport_height=base_h,
        device_scale_factor=scale,
        hardware_concurrency=random.choice([4, 8, 12, 16]),
        device_memory=random.choice([8, 16, 32]),
        platform=nav_platform,
        languages=lang_set,
        timezone=tz_entry["tz"],
        timezone_offset=tz_entry["offset"],
        locale=tz_entry["locale"],
        webgl_vendor=gpu["vendor"],
        webgl_renderer=gpu["renderer"],
        color_depth=24,
        max_touch_points=0,
    )


def get_stealth_script(fp: BrowserFingerprint) -> str:
    """Generate stealth injection script to mask automation indicators."""
    platform_escaped = fp.platform.replace("'", "\\'")

    return f"""
(() => {{
  // ─── Navigator Webdriver Flag ───
  try {{
    Object.defineProperty(navigator, 'webdriver', {{
      get: () => false,
      configurable: true,
      enumerable: true
    }});
  }} catch(e) {{}}

  // ─── Hardware & Platform ───
  try {{
    Object.defineProperty(navigator, 'platform', {{
      get: () => '{platform_escaped}',
      configurable: true
    }});
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
      get: () => {fp.hardware_concurrency},
      configurable: true
    }});
    Object.defineProperty(navigator, 'deviceMemory', {{
      get: () => {fp.device_memory},
      configurable: true
    }});
  }} catch(e) {{}}

  // ─── Languages ───
  try {{
    Object.defineProperty(navigator, 'languages', {{
      get: () => {json.dumps(fp.languages)},
      configurable: true
    }});
  }} catch(e) {{}}

  // ─── window.chrome Mock ───
  if (!window.chrome) {{
    window.chrome = {{}};
  }}
  window.chrome.runtime = window.chrome.runtime || {{}};
  window.chrome.loadTimes = window.chrome.loadTimes || function() {{
    return {{ requestTime: Date.now() / 1000, startLoadTime: Date.now() / 1000 }};
  }};
  window.chrome.csi = window.chrome.csi || function() {{
    return {{ startE: Date.now(), onloadT: Date.now() + 100, pageT: 150, tran: 15 }};
  }};

  // ─── Permissions Mock ───
  try {{
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => {{
      if (parameters.name === 'notifications') {{
        return Promise.resolve({{ state: Notification.permission }});
      }}
      return originalQuery(parameters);
    }};
  }} catch(e) {{}}

  // ─── Plugin Array Mock ───
  try {{
    Object.defineProperty(navigator, 'plugins', {{
      get: () => [1, 2, 3, 4, 5],
      configurable: true
    }});
  }} catch(e) {{}}

  // ─── WebGL Debug Renderer Info ───
  try {{
    const getParamHandler = {{
      apply: function(target, thisArg, args) {{
        const param = args[0];
        if (param === 37445) return '{fp.webgl_vendor}';
        if (param === 37446) return '{fp.webgl_renderer}';
        return Reflect.apply(target, thisArg, args);
      }}
    }};
    if (window.WebGLRenderingContext) {{
      WebGLRenderingContext.prototype.getParameter = new Proxy(
        WebGLRenderingContext.prototype.getParameter,
        getParamHandler
      );
    }}
    if (window.WebGL2RenderingContext) {{
      WebGL2RenderingContext.prototype.getParameter = new Proxy(
        WebGL2RenderingContext.prototype.getParameter,
        getParamHandler
      );
    }}
  }} catch(e) {{}}
}})();
"""


def get_context_options(fp: BrowserFingerprint) -> Dict[str, Any]:
    """Return Playwright context options for the fingerprint."""
    return {
        "viewport": {"width": fp.viewport_width, "height": fp.viewport_height},
        "device_scale_factor": fp.device_scale_factor,
        "locale": fp.locale,
        "timezone_id": fp.timezone,
        "user_agent": fp.user_agent,
    }


def get_launch_args() -> List[str]:
    """Return Chromium launch arguments for stealth operation."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
        "--disable-extensions",
        "--disable-popup-blocking",
    ]
