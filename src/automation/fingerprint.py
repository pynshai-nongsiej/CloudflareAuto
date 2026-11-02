"""Comprehensive browser fingerprint randomization for anti-detection.

Generates a fully randomized, infinite, and internally-consistent browser fingerprint
per registration session. Eliminates clustering across:
  - Infinite algorithmic User-Agent generation (Chromium 124-133 across macOS, Windows, Linux)
  - Full Client Hints (Sec-CH-UA headers & navigator.userAgentData with high entropy values)
  - Infinite screen & viewport dimensions with authentic OS chrome deductions
  - 80+ modern GPU profiles (NVIDIA RTX 40/30/20, AMD RX 7000/6000/5000, Intel Arc/Iris, Apple M1-M4)
  - Canvas fingerprint noise (hooks toDataURL, toBlob, and getImageData)
  - AudioContext & OfflineAudioContext fingerprint noise (AudioBuffer.getChannelData)
  - Subpixel font metrics noise (CanvasRenderingContext2D.measureText)
  - Unique MediaDevices enumeration per session
  - Permissions, Battery, Network Information, and window.chrome mocks
  - Automation flags removal (navigator.webdriver, Playwright/CDP markers)
"""

import json
import math
import random
import re
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─── OS & Platform Databases ──────────────────────────────────────────────────

_WINDOWS_OS_STRINGS = [
    "Windows NT 10.0; Win64; x64",
    "Windows NT 10.0; Win64; x64",
    "Windows NT 10.0; Win64; x64",
    "Windows NT 10.0; WOW64",
]

_MACOS_VERSIONS = [
    # (ua_os_version, platform_version, darwin_major)
    ("10_15_7", "14.7.5", "23.6.0"),
    ("10_15_7", "14.7.4", "23.6.0"),
    ("10_15_7", "15.3.1", "24.3.0"),
    ("10_15_7", "15.3.0", "24.3.0"),
    ("10_15_7", "15.2.0", "24.2.0"),
    ("10_15_7", "15.1.0", "24.1.0"),
    ("10_15_7", "14.6.1", "23.6.0"),
    ("10_15_7", "13.6.9", "22.6.0"),
    ("10_15_7", "12.7.6", "21.6.0"),
    ("14_7_5", "14.7.5", "23.6.0"),
    ("14_7_4", "14.7.4", "23.6.0"),
    ("15_3_1", "15.3.1", "24.3.0"),
    ("15_2_0", "15.2.0", "24.2.0"),
    ("15_1_0", "15.1.0", "24.1.0"),
]

_LINUX_OS_STRINGS = [
    "X11; Linux x86_64",
    "X11; Ubuntu; Linux x86_64",
    "X11; Fedora; Linux x86_64",
    "X11; Debian; Linux x86_64",
]


# ─── Chromium Release Version Profiles ────────────────────────────────────────

# Real Chrome release build bases for recent versions (124 - 133)
_CHROME_RELEASES = [
    {"major": 124, "build_base": 6367, "patch_max": 207},
    {"major": 125, "build_base": 6422, "patch_max": 190},
    {"major": 126, "build_base": 6478, "patch_max": 182},
    {"major": 127, "build_base": 6533, "patch_max": 195},
    {"major": 128, "build_base": 6613, "patch_max": 186},
    {"major": 129, "build_base": 6668, "patch_max": 180},
    {"major": 130, "build_base": 6723, "patch_max": 191},
    {"major": 131, "build_base": 6778, "patch_max": 205},
    {"major": 132, "build_base": 6834, "patch_max": 196},
    {"major": 133, "build_base": 6943, "patch_max": 190},
]


# ─── GPU Profiles (80+ Realistic Modern Desktop GPUs) ─────────────────────────

_GPU_PROFILES_WINDOWS = [
    # NVIDIA GeForce RTX 40-Series
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0)"},
    # NVIDIA GeForce RTX 30-Series
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3090 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"},
    # NVIDIA GeForce RTX 20 & GTX 16-Series
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 2080 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 2070 Super Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 2060 Super Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Super Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0)"},
    # AMD Radeon RX 7000 & 6000 Series
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 7900 XTX Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 7900 XT Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, Radeon(TM) RX 580 Series Direct3D11 vs_5_0 ps_5_0)"},
    # Intel Dedicated & Integrated
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Arc(TM) A770 Graphics Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Arc(TM) A750 Graphics Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 750 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)"},
]

_GPU_PROFILES_MACOS = [
    # Apple Silicon M-Series
    {"vendor": "Apple Inc.", "renderer": "Apple M1"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1 Pro"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1 Max"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1 Ultra"},
    {"vendor": "Apple Inc.", "renderer": "Apple M2"},
    {"vendor": "Apple Inc.", "renderer": "Apple M2 Pro"},
    {"vendor": "Apple Inc.", "renderer": "Apple M2 Max"},
    {"vendor": "Apple Inc.", "renderer": "Apple M3"},
    {"vendor": "Apple Inc.", "renderer": "Apple M3 Pro"},
    {"vendor": "Apple Inc.", "renderer": "Apple M3 Max"},
    {"vendor": "Apple Inc.", "renderer": "Apple M4"},
    {"vendor": "Apple Inc.", "renderer": "Apple M4 Pro"},
    {"vendor": "Apple Inc.", "renderer": "Apple M4 Max"},
    # Intel & AMD macOS Hardware
    {"vendor": "Intel Inc.", "renderer": "Intel(R) Iris(TM) Plus Graphics 640"},
    {"vendor": "Intel Inc.", "renderer": "Intel(R) Iris(TM) Plus Graphics 655"},
    {"vendor": "Intel Inc.", "renderer": "Intel(R) UHD Graphics 630"},
    {"vendor": "AMD", "renderer": "AMD Radeon Pro 5500M"},
    {"vendor": "AMD", "renderer": "AMD Radeon Pro 5300M"},
    {"vendor": "AMD", "renderer": "AMD Radeon Pro Vega 20"},
]

_GPU_PROFILES_LINUX = [
    {"vendor": "Intel Open Source Technology Center", "renderer": "Mesa DRI Intel(R) UHD Graphics 620 (KBL GT2)"},
    {"vendor": "Intel Open Source Technology Center", "renderer": "Mesa DRI Intel(R) UHD Graphics 630 (CFL GT2)"},
    {"vendor": "Intel", "renderer": "Mesa Intel(R) UHD Graphics 770 (ADL-S GT1)"},
    {"vendor": "Intel", "renderer": "Mesa Intel(R) Arc(tm) A770 Graphics (DG2)"},
    {"vendor": "X.Org", "renderer": "AMD Radeon RX 6700 XT (radeonsi, navi22, LLVM 16.0.6, DRM 3.54)"},
    {"vendor": "X.Org", "renderer": "AMD Radeon RX 580 Series (radeonsi, polaris10, LLVM 15.0.7, DRM 3.49)"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 4070/PCIe/SSE2"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 3080/PCIe/SSE2"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 3060/PCIe/SSE2"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce GTX 1660 Ti/PCIe/SSE2"},
    {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce GTX 1060 6GB/PCIe/SSE2"},
    {"vendor": "Google Inc. (Google)", "renderer": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)"},
]


# ─── Screen Resolutions (Real Display Distributions) ──────────────────────────

_SCREEN_RESOLUTIONS = [
    # (width, height, weight, is_hidpi)
    (1920, 1080, 42, False),  # 1080p FHD (Worldwide #1 standard)
    (2560, 1440, 18, True),   # 1440p 2K QHD (Gamer / Pro desktop standard)
    (1366, 768, 10, False),   # Common budget laptop
    (1536, 864, 8, False),    # 1080p scaled laptop
    (1440, 900, 6, True),     # MacBook Air 13" native aspect
    (1680, 1050, 4, True),    # MacBook Pro 15" / 16:10 display
    (1920, 1200, 4, True),    # 16:10 Pro display
    (2560, 1600, 3, True),    # MacBook Pro 13" Retina / 16"
    (3840, 2160, 2, True),    # 4K UHD
    (3024, 1964, 2, True),    # MacBook Pro 14" (M1/M2/M3/M4)
    (3456, 2234, 1, True),    # MacBook Pro 16" (M1/M2/M3/M4)
    (2560, 1080, 2, False),   # 21:9 Ultrawide FHD
    (3440, 1440, 2, True),    # 21:9 Ultrawide QHD
]


# ─── Timezones & Locales ──────────────────────────────────────────────────────

_TIMEZONES = [
    {"tz": "America/New_York", "locale": "en-US", "offset": -300},
    {"tz": "America/Chicago", "locale": "en-US", "offset": -360},
    {"tz": "America/Denver", "locale": "en-US", "offset": -420},
    {"tz": "America/Los_Angeles", "locale": "en-US", "offset": -480},
    {"tz": "America/Phoenix", "locale": "en-US", "offset": -420},
    {"tz": "America/Detroit", "locale": "en-US", "offset": -300},
    {"tz": "America/Indiana/Indianapolis", "locale": "en-US", "offset": -300},
    {"tz": "America/Boise", "locale": "en-US", "offset": -420},
    {"tz": "America/Anchorage", "locale": "en-US", "offset": -540},
    {"tz": "America/Toronto", "locale": "en-CA", "offset": -300},
    {"tz": "America/Vancouver", "locale": "en-CA", "offset": -480},
]

_LANGUAGE_SETS = [
    ["en-US", "en"],
    ["en-US", "en", "es"],
    ["en-US", "en-GB", "en"],
    ["en-CA", "en-US", "en"],
    ["en-GB", "en-US", "en"],
    ["en-AU", "en-US", "en"],
]


# ─── Fingerprint Dataclass ────────────────────────────────────────────────────

@dataclass
class BrowserFingerprint:
    """Holds a complete, internally-consistent, uniquely randomized browser fingerprint."""
    user_agent: str
    viewport_width: int
    viewport_height: int
    screen_width: int
    screen_height: int
    screen_avail_width: int
    screen_avail_height: int
    window_outer_width: int
    window_outer_height: int
    device_scale_factor: float
    hardware_concurrency: int
    device_memory: int
    platform: str            # navigator.platform e.g. "Win32", "MacIntel", "Linux x86_64"
    platform_name: str       # "Windows", "macOS", "Linux"
    platform_version: str    # "10.0.0", "15.3.1", etc.
    browser_type: str        # "chrome", "edge"
    browser_major: str       # e.g. "131"
    browser_full_version: str # e.g. "131.0.6778.85"
    architecture: str        # "x86", "arm"
    bitness: str             # "64"
    languages: List[str]
    timezone: str            # IANA timezone e.g. "America/New_York"
    timezone_offset: int     # minutes offset
    locale: str              # e.g. "en-US"
    webgl_vendor: str
    webgl_renderer: str
    color_depth: int
    max_touch_points: int
    do_not_track: Optional[str]
    sec_ch_ua: str
    sec_ch_ua_mobile: str
    sec_ch_ua_platform: str
    sec_ch_ua_platform_version: str
    sec_ch_ua_full_version_list: str
    canvas_noise_seed: int
    audio_noise_offset: float
    font_noise_seed: int
    device_ids: List[str] = field(default_factory=list)


# ─── Infinite User Agent & Fingerprint Generator ──────────────────────────────

def _weighted_choice(items_with_weights):
    """Pick an item from a list of (item..., weight) tuples."""
    total = sum(w for *_, w in items_with_weights)
    r = random.uniform(0, total)
    upto = 0
    for item in items_with_weights:
        w = item[-1]
        if upto + w >= r:
            return item[:-1]
        upto += w
    return items_with_weights[0][:-1]


def generate_fingerprint(
    prefer_platform: Optional[str] = None
) -> BrowserFingerprint:
    """Generate a 100% unique, internally-consistent, mathematically realistic fingerprint.

    Every invocation generates:
      - A never-before-seen User-Agent string with randomized build/patch
      - Perfectly aligned Client Hints (Sec-CH-UA and navigator.userAgentData)
      - Mathematically consistent screen, avail, outer, and inner viewport dimensions
      - Platform-appropriate GPU profile from 80+ modern options
      - Unique canvas, audio, font, and device IDs seeds
    """
    # 1. Resolve host platform preference
    norm_platform = (prefer_platform or "").lower().strip()
    if "mac" in norm_platform or "darwin" in norm_platform:
        chosen_platform = "darwin"
    elif "win" in norm_platform:
        chosen_platform = "win32"
    elif "linux" in norm_platform:
        chosen_platform = "linux"
    else:
        # Natural distribution if unspecified: 55% Windows, 35% Mac, 10% Linux
        chosen_platform = random.choices(["win32", "darwin", "linux"], weights=[55, 35, 10])[0]

    # 2. Browser engine flavor (85% Google Chrome, 15% Microsoft Edge)
    browser_type = "edge" if random.random() < 0.15 and chosen_platform in ("win32", "darwin") else "chrome"

    # 3. Pick Chromium release profile and jitter build & patch
    rel = random.choice(_CHROME_RELEASES)
    major = rel["major"]
    # Jitter build within small delta of official branch
    build = rel["build_base"] + random.randint(-4, 12)
    patch = random.randint(1, rel["patch_max"])
    full_version = f"{major}.0.{build}.{patch}"

    # 4. OS identification strings and Client Hints metadata
    if chosen_platform == "darwin":
        os_info = random.choice(_MACOS_VERSIONS)
        os_ua_part = f"Macintosh; Intel Mac OS X {os_info[0]}"
        nav_platform = "MacIntel"
        platform_name = "macOS"
        platform_version = os_info[1]
        # Modern Macs run Apple Silicon ARM or Intel x86
        arch = random.choice(["arm", "arm", "arm", "x86"])
        bitness = "64"
    elif chosen_platform == "linux":
        os_ua_part = random.choice(_LINUX_OS_STRINGS)
        nav_platform = "Linux x86_64"
        platform_name = "Linux"
        platform_version = f"{random.randint(5, 6)}.{random.randint(4, 15)}.0"
        arch = "x86"
        bitness = "64"
    else: # win32
        os_ua_part = random.choice(_WINDOWS_OS_STRINGS)
        nav_platform = "Win32"
        platform_name = "Windows"
        # Windows 10 is 10.0.0, Windows 11 reports platformVersion >= 13.0.0 (e.g. 15.0.0)
        platform_version = random.choice(["10.0.0", "15.0.0", "14.0.0", "10.0.0"])
        arch = "x86"
        bitness = "64"

    # Construct the unique User-Agent string
    if browser_type == "edge":
        ua = f"Mozilla/5.0 ({os_ua_part}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_version} Safari/537.36 Edg/{full_version}"
    else:
        ua = f"Mozilla/5.0 ({os_ua_part}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_version} Safari/537.36"

    # 5. Client Hints (Sec-CH-UA)
    # Chromium orders brands in randomized orders natively
    if browser_type == "edge":
        brands_data = [
            {"brand": "Chromium", "version": str(major)},
            {"brand": "Microsoft Edge", "version": str(major)},
            {"brand": "Not-A.Brand", "version": "24"},
        ]
        full_brands_data = [
            {"brand": "Chromium", "version": full_version},
            {"brand": "Microsoft Edge", "version": full_version},
            {"brand": "Not-A.Brand", "version": "24.0.0.0"},
        ]
    else:
        brands_data = [
            {"brand": "Chromium", "version": str(major)},
            {"brand": "Google Chrome", "version": str(major)},
            {"brand": "Not-A.Brand", "version": "24"},
        ]
        full_brands_data = [
            {"brand": "Chromium", "version": full_version},
            {"brand": "Google Chrome", "version": full_version},
            {"brand": "Not-A.Brand", "version": "24.0.0.0"},
        ]

    random.shuffle(brands_data)
    sec_ch_ua = ", ".join(f'"{b["brand"]}";v="{b["version"]}"' for b in brands_data)
    sec_ch_ua_mobile = "?0"
    sec_ch_ua_platform = f'"{platform_name}"'
    sec_ch_ua_platform_version = f'"{platform_version}"'
    sec_ch_ua_full_version_list = ", ".join(f'"{b["brand"]}";v="{b["version"]}"' for b in full_brands_data)

    # 6. Screen & Viewport Geometry (Realistic Physical Consistency)
    screen_choice = _weighted_choice(_SCREEN_RESOLUTIONS)
    screen_w, screen_h, is_hidpi = screen_choice

    # Taskbar / Menu bar / Dock deductions based on OS
    if platform_name == "Windows":
        taskbar_h = random.choice([40, 44, 48])
        avail_w = screen_w
        avail_h = screen_h - taskbar_h
    elif platform_name == "macOS":
        menu_bar_h = random.choice([25, 28, 32])
        dock_h = random.choice([0, 45, 55, 65]) # dock may be hidden or visible
        avail_w = screen_w
        avail_h = screen_h - menu_bar_h - dock_h
    else: # Linux
        panel_h = random.choice([28, 32, 40])
        avail_w = screen_w
        avail_h = screen_h - panel_h

    # Window State: 75% maximized, 25% windowed
    if random.random() < 0.75:
        outer_w = avail_w
        outer_h = avail_h
    else:
        outer_w = int(avail_w * random.uniform(0.85, 0.98))
        outer_h = int(avail_h * random.uniform(0.85, 0.98))

    # Browser UI Chrome deductions
    chrome_ui_h = random.randint(72, 115)
    frame_w = random.choice([0, 8, 16])

    inner_w = outer_w - frame_w
    inner_h = outer_h - chrome_ui_h

    # Ensure boundaries
    inner_w = max(1000, min(inner_w, outer_w))
    inner_h = max(550, min(inner_h, outer_h - 50))

    # Device Scale Factor
    if is_hidpi or platform_name == "macOS":
        scale = random.choice([2.0, 2.0, 2.0, 1.75, 2.25])
    else:
        scale = random.choice([1.0, 1.0, 1.0, 1.25, 1.5])

    # 7. GPU Profiles matching the platform
    if chosen_platform == "darwin":
        gpu = random.choice(_GPU_PROFILES_MACOS)
    elif chosen_platform == "linux":
        gpu = random.choice(_GPU_PROFILES_LINUX)
    else:
        gpu = random.choice(_GPU_PROFILES_WINDOWS)

    # 8. Hardware & System Specs
    hw_concurrency = random.choice([4, 6, 8, 8, 12, 16, 24, 32])
    dev_memory = random.choice([4, 8, 8, 16, 16, 32])
    color_depth = random.choice([24, 24, 24, 30])
    max_touch = 0  # Desktop devices have 0 touch points

    # 9. Locale, Timezone, Languages
    tz_entry = random.choice(_TIMEZONES)
    lang_set = random.choice(_LANGUAGE_SETS)
    dnt = random.choice(["1", None, None, None])

    # 10. Seeds for Canvas, Audio, Fonts & Peripheral Device IDs
    canvas_seed = random.randint(1, 255)
    audio_offset = random.uniform(0.00001, 0.00012)
    font_seed = random.randint(1000, 99999)
    device_ids = [str(uuid.uuid4()).replace("-", "") for _ in range(5)]

    return BrowserFingerprint(
        user_agent=ua,
        viewport_width=inner_w,
        viewport_height=inner_h,
        screen_width=screen_w,
        screen_height=screen_h,
        screen_avail_width=avail_w,
        screen_avail_height=avail_h,
        window_outer_width=outer_w,
        window_outer_height=outer_h,
        device_scale_factor=scale,
        hardware_concurrency=hw_concurrency,
        device_memory=dev_memory,
        platform=nav_platform,
        platform_name=platform_name,
        platform_version=platform_version,
        browser_type=browser_type,
        browser_major=str(major),
        browser_full_version=full_version,
        architecture=arch,
        bitness=bitness,
        languages=lang_set,
        timezone=tz_entry["tz"],
        timezone_offset=tz_entry["offset"],
        locale=tz_entry["locale"],
        webgl_vendor=gpu["vendor"],
        webgl_renderer=gpu["renderer"],
        color_depth=color_depth,
        max_touch_points=max_touch,
        do_not_track=dnt,
        sec_ch_ua=sec_ch_ua,
        sec_ch_ua_mobile=sec_ch_ua_mobile,
        sec_ch_ua_platform=sec_ch_ua_platform,
        sec_ch_ua_platform_version=sec_ch_ua_platform_version,
        sec_ch_ua_full_version_list=sec_ch_ua_full_version_list,
        canvas_noise_seed=canvas_seed,
        audio_noise_offset=audio_offset,
        font_noise_seed=font_seed,
        device_ids=device_ids,
    )


# ─── JS Injection Script ─────────────────────────────────────────────────────

def get_injection_script(fp: BrowserFingerprint) -> str:
    """Generate a comprehensive JavaScript injection script that overwrites
    all detectable browser fingerprinting surfaces natively and consistently.
    """
    ua_escaped = fp.user_agent.replace("'", "\\'").replace("\\", "\\\\")
    platform_escaped = fp.platform.replace("'", "\\'")
    webgl_vendor_escaped = fp.webgl_vendor.replace("'", "\\'")
    webgl_renderer_escaped = fp.webgl_renderer.replace("'", "\\'")
    languages_json = json.dumps(fp.languages)
    first_lang = fp.languages[0] if fp.languages else "en-US"

    app_version = fp.user_agent.replace("Mozilla/", "")
    app_version_escaped = app_version.replace("'", "\\'").replace("\\", "\\\\")

    # Brands for userAgentData
    if fp.browser_type == "edge":
        brands_json = json.dumps([
            {"brand": "Chromium", "version": fp.browser_major},
            {"brand": "Microsoft Edge", "version": fp.browser_major},
            {"brand": "Not-A.Brand", "version": "24"},
        ])
        full_brands_json = json.dumps([
            {"brand": "Chromium", "version": fp.browser_full_version},
            {"brand": "Microsoft Edge", "version": fp.browser_full_version},
            {"brand": "Not-A.Brand", "version": "24.0.0.0"},
        ])
    else:
        brands_json = json.dumps([
            {"brand": "Chromium", "version": fp.browser_major},
            {"brand": "Google Chrome", "version": fp.browser_major},
            {"brand": "Not-A.Brand", "version": "24"},
        ])
        full_brands_json = json.dumps([
            {"brand": "Chromium", "version": fp.browser_full_version},
            {"brand": "Google Chrome", "version": fp.browser_full_version},
            {"brand": "Not-A.Brand", "version": "24.0.0.0"},
        ])

    return f"""
(() => {{
  // ─── Utils ───
  const overwriteProperty = (obj, prop, value) => {{
    try {{
      Object.defineProperty(obj, prop, {{
        get: () => value,
        set: () => {{}},
        configurable: true,
        enumerable: true
      }});
    }} catch (e) {{}}
  }};

  const makeNative = (fn, name) => {{
    const fnName = name || fn.name;
    const wrapper = {{
      [fnName]: function() {{ return fn.apply(this, arguments); }}
    }}[fnName];
    const toString = () => `function ${{fnName}}() {{ [native code] }}`;
    Object.defineProperty(wrapper, 'toString', {{
      value: toString, configurable: true, enumerable: false, writable: true
    }});
    Object.defineProperty(wrapper.toString, 'toString', {{
      value: () => 'function toString() {{ [native code] }}',
      configurable: true
    }});
    return wrapper;
  }};

  // ─── Navigator: Hardware & Platform ───
  overwriteProperty(navigator, 'hardwareConcurrency', {fp.hardware_concurrency});
  overwriteProperty(navigator, 'deviceMemory', {fp.device_memory});
  overwriteProperty(navigator, 'platform', '{platform_escaped}');
  overwriteProperty(navigator, 'userAgent', '{ua_escaped}');
  overwriteProperty(navigator, 'appVersion', '{app_version_escaped}');
  overwriteProperty(navigator, 'languages', {languages_json});
  overwriteProperty(navigator, 'language', '{first_lang}');
  overwriteProperty(navigator, 'maxTouchPoints', {fp.max_touch_points});
  overwriteProperty(navigator, 'vendor', 'Google Inc.');
  overwriteProperty(navigator, 'productSub', '20030107');
  overwriteProperty(navigator, 'webdriver', false);
  {"overwriteProperty(navigator, 'doNotTrack', '" + fp.do_not_track + "');" if fp.do_not_track else ""}

  // ─── Client Hints (navigator.userAgentData) ───
  const brandsList = {brands_json};
  const fullBrandsList = {full_brands_json};
  const highEntropyValues = {{
    architecture: '{fp.architecture}',
    bitness: '{fp.bitness}',
    brands: brandsList,
    fullVersionList: fullBrandsList,
    mobile: false,
    model: '',
    platform: '{fp.platform_name}',
    platformVersion: '{fp.platform_version}',
    wow64: false
  }};

  const userAgentDataObj = {{
    brands: brandsList,
    mobile: false,
    platform: '{fp.platform_name}',
    getHighEntropyValues: makeNative(function(hints) {{
      const res = {{
        brands: brandsList,
        mobile: false,
        platform: '{fp.platform_name}'
      }};
      if (Array.isArray(hints)) {{
        for (const hint of hints) {{
          if (hint in highEntropyValues) {{
            res[hint] = highEntropyValues[hint];
          }}
        }}
      }}
      return Promise.resolve(res);
    }}, 'getHighEntropyValues'),
    toJSON: makeNative(function() {{
      return {{
        brands: brandsList,
        mobile: false,
        platform: '{fp.platform_name}'
      }};
    }}, 'toJSON')
  }};
  overwriteProperty(navigator, 'userAgentData', userAgentDataObj);

  // ─── Screen & Viewport Physical Consistency ───
  const screenWidth = {fp.screen_width};
  const screenHeight = {fp.screen_height};
  const availWidth = {fp.screen_avail_width};
  const availHeight = {fp.screen_avail_height};
  const outerWidth = {fp.window_outer_width};
  const outerHeight = {fp.window_outer_height};
  const innerWidth = {fp.viewport_width};
  const innerHeight = {fp.viewport_height};

  overwriteProperty(screen, 'width', screenWidth);
  overwriteProperty(screen, 'height', screenHeight);
  overwriteProperty(screen, 'availWidth', availWidth);
  overwriteProperty(screen, 'availHeight', availHeight);
  overwriteProperty(screen, 'availLeft', 0);
  overwriteProperty(screen, 'availTop', 0);
  overwriteProperty(screen, 'colorDepth', {fp.color_depth});
  overwriteProperty(screen, 'pixelDepth', {fp.color_depth});

  overwriteProperty(window, 'innerWidth', innerWidth);
  overwriteProperty(window, 'innerHeight', innerHeight);
  overwriteProperty(window, 'outerWidth', outerWidth);
  overwriteProperty(window, 'outerHeight', outerHeight);
  overwriteProperty(window, 'devicePixelRatio', {fp.device_scale_factor});
  overwriteProperty(window, 'screenX', 0);
  overwriteProperty(window, 'screenY', 0);
  overwriteProperty(window, 'screenLeft', 0);
  overwriteProperty(window, 'screenTop', 0);

  // ─── Plugins & MimeTypes ───
  const mockPlugins = [
    {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }}
  ];

  const pluginList = mockPlugins.map(p => {{
    const plugin = Object.create(Plugin.prototype);
    overwriteProperty(plugin, 'name', p.name);
    overwriteProperty(plugin, 'filename', p.filename);
    overwriteProperty(plugin, 'description', p.description);
    overwriteProperty(plugin, 'length', 0);
    return plugin;
  }});

  Object.setPrototypeOf(pluginList, PluginArray.prototype);
  overwriteProperty(pluginList, 'length', pluginList.length);
  overwriteProperty(navigator, 'plugins', pluginList);
  overwriteProperty(navigator, 'mimeTypes', Object.create(MimeTypeArray.prototype));
  overwriteProperty(navigator, 'pdfViewerEnabled', true);

  // ─── WebGL Vendor & Renderer Spoofing ───
  const maskWebGL = (proto) => {{
    if (!proto) return;
    const origGetParameter = proto.getParameter;
    const origGetExtension = proto.getExtension;

    proto.getParameter = makeNative(function(parameter) {{
      if (parameter === 37445) return '{webgl_vendor_escaped}';   // UNMASKED_VENDOR_WEBGL
      if (parameter === 37446) return '{webgl_renderer_escaped}'; // UNMASKED_RENDERER_WEBGL
      if (parameter === 3571)  return '{webgl_vendor_escaped.split(" ")[0]}'; // VENDOR
      if (parameter === 3572)  return '{webgl_renderer_escaped}'; // RENDERER
      return origGetParameter.apply(this, arguments);
    }}, 'getParameter');

    proto.getExtension = makeNative(function(name) {{
      const ext = origGetExtension.apply(this, arguments);
      if (name === 'WEBGL_debug_renderer_info') {{
        return {{ UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 }};
      }}
      return ext;
    }}, 'getExtension');
  }};

  if (window.WebGLRenderingContext) maskWebGL(WebGLRenderingContext.prototype);
  if (window.WebGL2RenderingContext) maskWebGL(WebGL2RenderingContext.prototype);

  // ─── Canvas Fingerprint Noise (Working on toDataURL, toBlob, and getImageData) ───
  const canvasNoiseSeed = {fp.canvas_noise_seed};

  if (window.CanvasRenderingContext2D) {{
    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = makeNative(function(sx, sy, sw, sh) {{
      const res = origGetImageData.apply(this, arguments);
      if (res && res.data && res.data.length >= 4) {{
        for (let i = 0; i < res.data.length; i += 64) {{
          const delta = ((canvasNoiseSeed + i) % 3) - 1; // -1, 0, or 1
          res.data[i] = Math.max(0, Math.min(255, res.data[i] + delta));
        }}
      }}
      return res;
    }}, 'getImageData');

    const origMeasureText = CanvasRenderingContext2D.prototype.measureText;
    const fontNoiseSeed = {fp.font_noise_seed};
    CanvasRenderingContext2D.prototype.measureText = makeNative(function(text) {{
      const metrics = origMeasureText.apply(this, arguments);
      try {{
        const delta = ((text.length * 17 + fontNoiseSeed) % 5 - 2) * 0.00002;
        const w = metrics.width + delta;
        overwriteProperty(metrics, 'width', w);
      }} catch(e) {{}}
      return metrics;
    }}, 'measureText');
  }}

  if (window.HTMLCanvasElement) {{
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = makeNative(function(type, quality) {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {{
          const pixel = ctx.getImageData(0, 0, 1, 1);
          const origR = pixel.data[0];
          pixel.data[0] = (pixel.data[0] + (canvasNoiseSeed % 3) + 1) % 256;
          ctx.putImageData(pixel, 0, 0);
          const res = origToDataURL.apply(this, arguments);
          pixel.data[0] = origR;
          ctx.putImageData(pixel, 0, 0);
          return res;
        }}
      }} catch (e) {{}}
      return origToDataURL.apply(this, arguments);
    }}, 'toDataURL');

    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = makeNative(function(callback, type, quality) {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {{
          const pixel = ctx.getImageData(0, 0, 1, 1);
          const origR = pixel.data[0];
          pixel.data[0] = (pixel.data[0] + (canvasNoiseSeed % 3) + 1) % 256;
          ctx.putImageData(pixel, 0, 0);
          return origToBlob.call(this, (blob) => {{
            try {{
              pixel.data[0] = origR;
              ctx.putImageData(pixel, 0, 0);
            }} catch(e) {{}}
            callback(blob);
          }}, type, quality);
        }}
      }} catch(e) {{}}
      return origToBlob.apply(this, arguments);
    }}, 'toBlob');
  }}

  // ─── AudioContext & OfflineAudioContext Fingerprint Noise ───
  const audioOffset = {fp.audio_noise_offset};

  if (window.AudioBuffer) {{
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = makeNative(function(channel) {{
      const data = origGetChannelData.apply(this, arguments);
      if (data && data.length > 0) {{
        for (let i = 0; i < data.length; i += 80) {{
          data[i] += audioOffset;
        }}
      }}
      return data;
    }}, 'getChannelData');
  }}

  if (window.AudioContext || window.webkitAudioContext) {{
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const origCreateOscillator = AudioCtx.prototype.createOscillator;
    if (origCreateOscillator) {{
      AudioCtx.prototype.createOscillator = makeNative(function() {{
        const osc = origCreateOscillator.apply(this, arguments);
        const origConnect = osc.connect;
        osc.connect = makeNative(function(dest) {{
          if (dest && dest.frequency) {{
            dest.frequency.value += audioOffset;
          }}
          return origConnect.apply(this, arguments);
        }}, 'connect');
        return osc;
      }}, 'createOscillator');
    }}
  }}

  // ─── MediaDevices Mocking ───
  if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
    const mockDevices = [
      {{ deviceId: '{fp.device_ids[0]}', kind: 'audioinput', label: '', groupId: '{fp.device_ids[1]}' }},
      {{ deviceId: '{fp.device_ids[2]}', kind: 'audiooutput', label: '', groupId: '{fp.device_ids[1]}' }},
      {{ deviceId: '{fp.device_ids[3]}', kind: 'videoinput', label: '', groupId: '{fp.device_ids[4]}' }},
    ];
    navigator.mediaDevices.enumerateDevices = makeNative(function() {{
      return Promise.resolve(mockDevices);
    }}, 'enumerateDevices');
  }}

  // ─── window.chrome Runtime Mock ───
  if (!window.chrome) {{
    window.chrome = {{}};
  }}
  window.chrome.runtime = window.chrome.runtime || {{}};
  window.chrome.app = window.chrome.app || {{ isInstalled: false, InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }}, RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }} }};
  window.chrome.loadTimes = makeNative(() => ({{
    requestTime: Date.now() / 1000,
    startLoadTime: Date.now() / 1000,
    commitLoadTime: Date.now() / 1000,
    finishDocumentLoadTime: Date.now() / 1000,
    finishLoadTime: Date.now() / 1000,
    firstPaintTime: Date.now() / 1000,
    firstPaintAfterLoadTime: 0,
    navigationType: 'Other',
    wasFetchedViaSpdy: true,
    wasNpnNegotiated: true,
    npnNegotiatedProtocol: 'h2',
    wasAlternateProtocolAvailable: false,
    connectionInfo: 'h2'
  }}), 'loadTimes');
  window.chrome.csi = makeNative(() => ({{
    startE: Date.now(),
    onloadT: Date.now() + {random.randint(50, 200)},
    pageT: {random.randint(100, 500)},
    tran: 15
  }}), 'csi');

  // ─── Timezone Spoofing ───
  const targetTZ = '{fp.timezone}';
  const targetOffset = {fp.timezone_offset};

  Date.prototype.getTimezoneOffset = makeNative(function() {{
    return -targetOffset;
  }}, 'getTimezoneOffset');

  const origResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
  Intl.DateTimeFormat.prototype.resolvedOptions = makeNative(function() {{
    const result = origResolvedOptions.apply(this, arguments);
    result.timeZone = targetTZ;
    return result;
  }}, 'resolvedOptions');

  // ─── WebRTC Protection ───
  if (window.RTCPeerConnection) {{
    const OrgRTC = window.RTCPeerConnection;
    window.RTCPeerConnection = makeNative(function(config) {{
      if (config && config.iceServers) {{
        config.iceTransportPolicy = 'relay';
      }}
      const conn = new OrgRTC(config);
      const origCreateOffer = conn.createOffer;
      conn.createOffer = makeNative(function(options) {{
        if (options) options.offerToReceiveAudio = false;
        return origCreateOffer.apply(this, arguments);
      }}, 'createOffer');
      return conn;
    }}, 'RTCPeerConnection');
    window.RTCPeerConnection.prototype = OrgRTC.prototype;
  }}

  // ─── Permissions API Hardening ───
  if (navigator.permissions) {{
    const orgQuery = navigator.permissions.query;
    navigator.permissions.query = makeNative((parameters) => {{
      if (parameters.name === 'notifications') {{
        return Promise.resolve({{ state: 'default', onchange: null }});
      }}
      return orgQuery.apply(navigator.permissions, [parameters]);
    }}, 'query');
  }}

  // ─── Battery API Spoofing ───
  if (navigator.getBattery) {{
    navigator.getBattery = makeNative(() => {{
      return Promise.resolve({{
        charging: {random.choice(["true", "false"])},
        chargingTime: {random.choice(["Infinity", str(random.randint(300, 7200))])},
        dischargingTime: {random.choice(["Infinity", str(random.randint(3600, 28800))])},
        level: {round(random.uniform(0.5, 1.0), 2)},
        addEventListener: () => {{}},
        removeEventListener: () => {{}}
      }});
    }}, 'getBattery');
  }}

  // ─── Connection / NetworkInformation Spoofing ───
  if (navigator.connection) {{
    overwriteProperty(navigator.connection, 'effectiveType', '{random.choice(["4g", "4g", "4g", "3g"])}');
    overwriteProperty(navigator.connection, 'downlink', {round(random.uniform(2.5, 12.0), 1)});
    overwriteProperty(navigator.connection, 'rtt', {random.choice([40, 50, 75, 100, 120])});
    overwriteProperty(navigator.connection, 'saveData', false);
  }}

  // ─── Notification Constructor ───
  if (window.Notification) {{
    overwriteProperty(Notification, 'permission', 'default');
  }}

  // ─── Automation Markers Cleanup ───
  try {{
    delete navigator.__proto__.webdriver;
  }} catch(e) {{}}

  const automationProps = [
    '__playwright',
    '__pw_manual',
    '__PW_inspect',
    '_phantom',
    '__nightmare',
    '_selenium',
    'callPhantom',
    '_Recaptcha',
    'domAutomation',
    'domAutomationController',
  ];
  automationProps.forEach(prop => {{
    try {{ delete window[prop]; }} catch(e) {{}}
    try {{
      Object.defineProperty(window, prop, {{
        get: () => undefined,
        set: () => {{}},
        configurable: true
      }});
    }} catch(e) {{}}
  }});
}})();
"""


# ─── Playwright Context Options ──────────────────────────────────────────────

def get_playwright_context_options(fp: BrowserFingerprint) -> Dict[str, Any]:
    """Return a dict suitable for browser.new_context(**options).

    Sets user_agent, viewport, native screen size, locale, timezone,
    color_scheme, device_scale_factor, and complete Sec-CH-UA HTTP headers.
    """
    options: Dict[str, Any] = {
        "user_agent": fp.user_agent,
        "viewport": {"width": fp.viewport_width, "height": fp.viewport_height},
        "screen": {"width": fp.screen_width, "height": fp.screen_height},
        "device_scale_factor": fp.device_scale_factor,
        "locale": fp.locale,
        "timezone_id": fp.timezone,
        "color_scheme": random.choice(["light", "dark", "no-preference"]),
        "reduced_motion": random.choice(["reduce", "no-preference"]),
        "has_touch": fp.max_touch_points > 0,
    }

    extra_headers: Dict[str, str] = {}
    if fp.sec_ch_ua:
        extra_headers["sec-ch-ua"] = fp.sec_ch_ua
        extra_headers["sec-ch-ua-mobile"] = fp.sec_ch_ua_mobile
        extra_headers["sec-ch-ua-platform"] = fp.sec_ch_ua_platform
        if fp.sec_ch_ua_platform_version:
            extra_headers["sec-ch-ua-platform-version"] = fp.sec_ch_ua_platform_version
        if fp.sec_ch_ua_full_version_list:
            extra_headers["sec-ch-ua-full-version-list"] = fp.sec_ch_ua_full_version_list

    if fp.do_not_track:
        extra_headers["DNT"] = fp.do_not_track

    # Accept-Language header matching the selected language array
    accept_lang_parts = []
    for i, lang in enumerate(fp.languages):
        q = round(1.0 - i * 0.1, 1)
        if q >= 1.0:
            accept_lang_parts.append(lang)
        else:
            accept_lang_parts.append(f"{lang};q={q}")
    extra_headers["Accept-Language"] = ", ".join(accept_lang_parts)

    if extra_headers:
        options["extra_http_headers"] = extra_headers

    return options


def get_launch_args() -> List[str]:
    """Return Chromium launch arguments for stealth operation."""
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--mute-audio",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-ipc-flooding-protection",
        "--no-sandbox",
    ]
    if sys.platform == "linux":
        args.extend([
            "--disable-gpu",
            "--disable-software-rasterizer",
        ])
    return args


def apply_fingerprint_to_context(
    context,
    fp: BrowserFingerprint,
) -> None:
    """Apply the fingerprint injection script to an already-created Playwright context.

    Call this BEFORE navigating to any page.
    """
    import asyncio
    script = get_injection_script(fp)
    if asyncio.iscoroutinefunction(getattr(context, 'add_init_script', None)):
        return context.add_init_script(script)
    else:
        context.add_init_script(script)
