"""Comprehensive browser fingerprint randomization for anti-detection.

Ported and expanded from trafficbot's FingerprintService.ts.
Generates a fully randomized, internally-consistent browser fingerprint
and provides both a Playwright-injectable JS script and context options.

Randomizes:
  - User-Agent string (with minor/build version jitter)
  - Viewport dimensions
  - Device pixel ratio / scale factor
  - Hardware concurrency (CPU cores)
  - Device memory (RAM)
  - Navigator platform
  - Accept-Language / navigator.languages
  - Timezone (with consistent locale)
  - WebGL vendor / renderer (GPU)
  - Navigator plugins & mimeTypes
  - Canvas pixel noise (anti-canvas-fingerprint)
  - WebRTC IP leak protection
  - window.chrome runtime mock
  - navigator.webdriver flag removal
  - Permissions API hardening
  - Sec-CH-UA client hint headers
  - AudioContext fingerprint noise
  - Battery API spoofing
  - Connection/NetworkInformation spoofing
"""

import math
import random
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─── User Agent Database ─────────────────────────────────────────────────────

_UA_DATABASE: List[Dict[str, str]] = [
    # Chrome on Windows
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36", "platform": "win32", "browser": "chrome"},
    # Chrome on macOS
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36", "platform": "darwin", "browser": "chrome"},
    # Chrome on Linux
    {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36", "platform": "linux", "browser": "chrome"},
    {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36", "platform": "linux", "browser": "chrome"},
    # Firefox
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0", "platform": "win32", "browser": "firefox"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:135.0) Gecko/20100101 Firefox/135.0", "platform": "darwin", "browser": "firefox"},
    {"ua": "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0", "platform": "linux", "browser": "firefox"},
    # Safari
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15", "platform": "darwin", "browser": "safari"},
    # Edge
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0", "platform": "win32", "browser": "edge"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0", "platform": "darwin", "browser": "edge"},
]


# ─── GPU Profiles ─────────────────────────────────────────────────────────────

_GPU_PROFILES = [
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Ti Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, Radeon(TM) RX 580 Series Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1"},
    {"vendor": "Apple Inc.", "renderer": "Apple M2"},
    {"vendor": "Apple Inc.", "renderer": "Apple M3"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1 Pro"},
    {"vendor": "Intel Inc.", "renderer": "Intel(R) Iris(TM) Plus Graphics 640"},
    {"vendor": "Intel Inc.", "renderer": "Intel(R) Iris(TM) Plus Graphics 655"},
]


# ─── Timezone pools ───────────────────────────────────────────────────────────

_TIMEZONES = [
    {"tz": "America/New_York", "locale": "en-US", "offset": -300},
    {"tz": "America/Chicago", "locale": "en-US", "offset": -360},
    {"tz": "America/Denver", "locale": "en-US", "offset": -420},
    {"tz": "America/Los_Angeles", "locale": "en-US", "offset": -480},
    {"tz": "Europe/London", "locale": "en-GB", "offset": 0},
    {"tz": "Europe/Berlin", "locale": "de-DE", "offset": 60},
    {"tz": "Europe/Paris", "locale": "fr-FR", "offset": 60},
    {"tz": "Asia/Tokyo", "locale": "ja-JP", "offset": 540},
    {"tz": "Australia/Sydney", "locale": "en-AU", "offset": 600},
    {"tz": "America/Toronto", "locale": "en-CA", "offset": -300},
]


# ─── Language pools ───────────────────────────────────────────────────────────

_LANGUAGE_SETS = [
    ["en-US", "en"],
    ["en-US", "en", "es"],
    ["en-GB", "en"],
    ["en-CA", "en", "fr"],
    ["en-AU", "en"],
    ["de-DE", "de", "en"],
    ["fr-FR", "fr", "en"],
    ["es-ES", "es", "en"],
    ["pt-BR", "pt", "en"],
    ["ja-JP", "ja", "en"],
]


# ─── Viewport presets (common real screen resolutions) ────────────────────────

_VIEWPORT_PRESETS = [
    (1366, 768), (1440, 900), (1536, 864), (1920, 1080),
    (1280, 720), (1280, 800), (1600, 900), (1680, 1050),
    (1920, 1200), (2560, 1440),
]


# ─── Fingerprint Dataclass ────────────────────────────────────────────────────

@dataclass
class BrowserFingerprint:
    """Holds a complete, internally-consistent randomized browser fingerprint."""
    user_agent: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    hardware_concurrency: int
    device_memory: int
    platform: str            # navigator.platform e.g. "Win32", "MacIntel", "Linux x86_64"
    languages: List[str]
    timezone: str            # IANA timezone e.g. "America/New_York"
    timezone_offset: int     # minutes offset
    locale: str              # e.g. "en-US"
    webgl_vendor: str
    webgl_renderer: str
    color_depth: int
    max_touch_points: int
    do_not_track: Optional[str]  # "1", "0", or None (unset)
    # Sec-CH-UA header fields
    sec_ch_ua: str
    sec_ch_ua_mobile: str
    sec_ch_ua_platform: str
    # Canvas noise seed
    canvas_noise_seed: int
    # Audio noise
    audio_noise_offset: float


# ─── Generator ────────────────────────────────────────────────────────────────

def _randomize_chrome_version(ua: str) -> str:
    """Randomize minor/build/patch for Chrome and Edge version strings.
    
    Example: Chrome/145.0.0.0 → Chrome/145.0.4285.12
    """
    import re
    build = random.randint(1000, 5999)
    patch = random.randint(0, 199)

    # Chrome version
    ua = re.sub(
        r'Chrome/(\d+)\.0\.0\.0',
        lambda m: f'Chrome/{m.group(1)}.0.{build}.{patch}',
        ua
    )
    # Edge version
    ua = re.sub(
        r'Edg/(\d+)\.0\.0\.0',
        lambda m: f'Edg/{m.group(1)}.0.{build}.{patch}',
        ua
    )
    return ua


def generate_fingerprint(
    prefer_platform: Optional[str] = None
) -> BrowserFingerprint:
    """Generate a fully randomized, internally-consistent browser fingerprint.
    
    Args:
        prefer_platform: Optional hint for host platform ('darwin', 'win32', 'linux').
                         If provided, UAs matching this platform are preferred.
    
    Returns:
        A BrowserFingerprint with all fields randomized.
    """
    # 1. Select a random UA entry, preferring the host platform if given
    if prefer_platform:
        filtered = [e for e in _UA_DATABASE if e["platform"] == prefer_platform]
        pool = filtered if filtered else _UA_DATABASE
    else:
        pool = _UA_DATABASE
    
    entry = random.choice(pool)
    ua = _randomize_chrome_version(entry["ua"])
    browser = entry.get("browser", "chrome")

    # 2. Resolve navigator.platform from UA string
    if "Macintosh" in ua or "Mac OS X" in ua:
        nav_platform = "MacIntel"
    elif "Linux" in ua:
        nav_platform = "Linux x86_64"
    else:
        nav_platform = "Win32"

    # 3. Pick a GPU profile consistent with the platform
    if nav_platform == "MacIntel":
        gpu_pool = [p for p in _GPU_PROFILES if "Apple" in p["vendor"] or "Intel" in p["vendor"]]
    elif nav_platform == "Win32":
        gpu_pool = [p for p in _GPU_PROFILES if "Google" in p["vendor"] or "NVIDIA" in p["vendor"] or "AMD" in p["vendor"]]
    else:
        gpu_pool = _GPU_PROFILES
    
    gpu = random.choice(gpu_pool)

    # 4. Viewport with slight randomization around a common resolution
    base_w, base_h = random.choice(_VIEWPORT_PRESETS)
    vp_w = base_w + random.randint(-20, 20)
    vp_h = base_h + random.randint(-20, 20)

    # 5. Scale factor
    if nav_platform == "MacIntel":
        scale = 2.0  # Retina
    else:
        scale = random.choice([1.0, 1.0, 1.0, 1.25, 1.5, 2.0])

    # 6. Hardware
    hw_concurrency = random.choice([2, 4, 4, 6, 8, 8, 12, 16])
    dev_memory = random.choice([4, 8, 8, 16, 16, 32])

    # 7. Languages & timezone
    lang_set = random.choice(_LANGUAGE_SETS)
    tz_entry = random.choice(_TIMEZONES)

    # 8. Color depth
    color_depth = random.choice([24, 24, 24, 30, 32])

    # 9. Touch points (0 for desktops)
    max_touch = 0

    # 10. DNT header
    dnt = random.choice(["1", None, None, None])

    # 11. Build Sec-CH-UA headers
    import re
    chrome_match = re.search(r'Chrome/(\d+)', ua)
    if chrome_match and browser in ("chrome", "edge"):
        major = chrome_match.group(1)
        is_mobile = "Mobile" in ua
        ch_platform = {"MacIntel": "macOS", "Win32": "Windows", "Linux x86_64": "Linux"}.get(nav_platform, "Windows")
        
        # Randomize brand order and use current-era brands
        brands = [
            f'"Chromium";v="{major}"',
            f'"Google Chrome";v="{major}"',
            f'"Not(A:Brand";v="99"',
        ]
        if browser == "edge":
            brands[1] = f'"Microsoft Edge";v="{major}"'
        random.shuffle(brands)
        sec_ch_ua = ", ".join(brands)
        sec_ch_ua_mobile = "?1" if is_mobile else "?0"
        sec_ch_ua_platform = f'"{ch_platform}"'
    else:
        sec_ch_ua = ""
        sec_ch_ua_mobile = "?0"
        sec_ch_ua_platform = '"Unknown"'

    # 12. Canvas & Audio noise seeds
    canvas_seed = random.randint(1, 255)
    audio_offset = random.uniform(0.00001, 0.0001)

    return BrowserFingerprint(
        user_agent=ua,
        viewport_width=vp_w,
        viewport_height=vp_h,
        device_scale_factor=scale,
        hardware_concurrency=hw_concurrency,
        device_memory=dev_memory,
        platform=nav_platform,
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
        canvas_noise_seed=canvas_seed,
        audio_noise_offset=audio_offset,
    )


# ─── JS Injection Script ─────────────────────────────────────────────────────

def get_injection_script(fp: BrowserFingerprint) -> str:
    """Generate a comprehensive JavaScript injection script that overwrites
    all detectable browser fingerprinting surfaces.
    
    Must be injected via page.add_init_script() or evaluateOnNewDocument().
    """
    # Escape for safe embedding in JS template
    ua_escaped = fp.user_agent.replace("'", "\\'").replace("\\", "\\\\")
    platform_escaped = fp.platform.replace("'", "\\'")
    webgl_vendor_escaped = fp.webgl_vendor.replace("'", "\\'")
    webgl_renderer_escaped = fp.webgl_renderer.replace("'", "\\'")
    languages_json = json.dumps(fp.languages)
    first_lang = fp.languages[0] if fp.languages else "en-US"

    # Compute appVersion from UA
    app_version = fp.user_agent.replace("Mozilla/", "")
    app_version_escaped = app_version.replace("'", "\\'").replace("\\", "\\\\")

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

  // ─── Screen & Viewport Consistency ───
  const screenWidth = {fp.viewport_width};
  const screenHeight = {fp.viewport_height};
  overwriteProperty(screen, 'width', screenWidth);
  overwriteProperty(screen, 'height', screenHeight);
  overwriteProperty(screen, 'availWidth', screenWidth);
  overwriteProperty(screen, 'availHeight', screenHeight - {random.randint(30, 50)});
  overwriteProperty(screen, 'availLeft', 0);
  overwriteProperty(screen, 'availTop', 0);
  overwriteProperty(screen, 'colorDepth', {fp.color_depth});
  overwriteProperty(screen, 'pixelDepth', {fp.color_depth});
  overwriteProperty(window, 'innerWidth', screenWidth);
  overwriteProperty(window, 'innerHeight', screenHeight - {random.randint(70, 110)});
  overwriteProperty(window, 'outerWidth', screenWidth + {random.randint(0, 16)});
  overwriteProperty(window, 'outerHeight', screenHeight + {random.randint(60, 90)});
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

  // ─── Canvas Fingerprint Noise ───
  const canvasNoiseSeed = {fp.canvas_noise_seed};
  const manipulateCanvas = (proto) => {{
    if (!proto) return;
    const origGetImageData = proto.getImageData;
    proto.getImageData = makeNative(function() {{
      const res = origGetImageData.apply(this, arguments);
      if (res && res.data && res.data.length >= 4) {{
        // Apply deterministic noise based on seed
        for (let i = 0; i < Math.min(res.data.length, 16); i += 4) {{
          res.data[i] = (res.data[i] + canvasNoiseSeed + i) % 256;
        }}
      }}
      return res;
    }}, 'getImageData');

    const origToDataURL = proto.canvas?.constructor?.prototype?.toDataURL;
    // Noise via toBlob as well
    if (proto.canvas && proto.canvas.constructor) {{
      const origToBlob = proto.canvas.constructor.prototype.toBlob;
      if (origToBlob) {{
        proto.canvas.constructor.prototype.toBlob = makeNative(function() {{
          // Inject 1px noise before conversion
          try {{
            const ctx = this.getContext('2d');
            if (ctx) {{
              const pixel = ctx.getImageData(0, 0, 1, 1);
              pixel.data[0] = (pixel.data[0] + canvasNoiseSeed) % 256;
              ctx.putImageData(pixel, 0, 0);
            }}
          }} catch(e) {{}}
          return origToBlob.apply(this, arguments);
        }}, 'toBlob');
      }}
    }}
  }};

  if (window.CanvasRenderingContext2D) manipulateCanvas(CanvasRenderingContext2D.prototype);

  // ─── AudioContext Fingerprint Noise ───
  if (window.AudioContext || window.webkitAudioContext) {{
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const origCreateOscillator = AudioCtx.prototype.createOscillator;
    const origCreateDynamicsCompressor = AudioCtx.prototype.createDynamicsCompressor;
    const audioOffset = {fp.audio_noise_offset};

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

    AudioCtx.prototype.createDynamicsCompressor = makeNative(function() {{
      const comp = origCreateDynamicsCompressor.apply(this, arguments);
      const origGetFreqResponse = comp.getFrequencyResponse;
      if (origGetFreqResponse) {{
        comp.getFrequencyResponse = makeNative(function(freqArray, magArray, phaseArray) {{
          origGetFreqResponse.apply(this, arguments);
          if (magArray && magArray.length > 0) {{
            for (let i = 0; i < magArray.length; i++) {{
              magArray[i] += audioOffset;
            }}
          }}
        }}, 'getFrequencyResponse');
      }}
      return comp;
    }}, 'createDynamicsCompressor');
  }}

  // ─── window.chrome Runtime Mock ───
  if (!window.chrome) {{
    window.chrome = {{}};
  }}
  window.chrome.runtime = window.chrome.runtime || {{}};
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
  
  const origDateGetTimezoneOffset = Date.prototype.getTimezoneOffset;
  Date.prototype.getTimezoneOffset = makeNative(function() {{
    return -targetOffset;
  }}, 'getTimezoneOffset');

  const origResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
  Intl.DateTimeFormat.prototype.resolvedOptions = makeNative(function() {{
    const result = origResolvedOptions.apply(this, arguments);
    result.timeZone = targetTZ;
    return result;
  }}, 'resolvedOptions');

  // ─── WebRTC IP Leak Protection ───
  if (window.RTCPeerConnection) {{
    const OrgRTC = window.RTCPeerConnection;
    window.RTCPeerConnection = makeNative(function(config) {{
      // Force TURN-only ICE to prevent local IP leaks
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
    overwriteProperty(navigator.connection, 'downlink', {round(random.uniform(1.5, 10.0), 1)});
    overwriteProperty(navigator.connection, 'rtt', {random.choice([50, 100, 100, 150, 200])});
    overwriteProperty(navigator.connection, 'saveData', false);
  }}

  // ─── Notification Constructor ───
  if (window.Notification) {{
    overwriteProperty(Notification, 'permission', 'default');
  }}

  // ─── Speech Synthesis ───
  // Prevent empty speechSynthesis.getVoices() from being a tell
  if (window.speechSynthesis) {{
    const origGetVoices = speechSynthesis.getVoices;
    speechSynthesis.getVoices = makeNative(function() {{
      const voices = origGetVoices.apply(this, arguments);
      return voices.length > 0 ? voices : [{{
        default: true,
        lang: '{first_lang}',
        localService: true,
        name: 'Native',
        voiceURI: 'Native'
      }}];
    }}, 'getVoices');
  }}

  // ─── Automation Markers Cleanup ───
  // Remove residual automation properties
  try {{
    delete navigator.__proto__.webdriver;
  }} catch(e) {{}}
  
  // Remove Playwright/Puppeteer tell-tales
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

  // Clean up stack traces that might reveal headless
  const origError = Error;
  const cleanStack = (stack) => {{
    if (!stack) return stack;
    return stack.split('\\n').filter(line => 
      !line.includes('puppeteer') && 
      !line.includes('playwright') && 
      !line.includes('HeadlessChrome')
    ).join('\\n');
  }};
}})();
"""


# ─── Playwright Context Options ──────────────────────────────────────────────

def get_playwright_context_options(fp: BrowserFingerprint) -> Dict[str, Any]:
    """Return a dict suitable for browser.new_context(**options).
    
    Includes user_agent, viewport, locale, timezone, color_scheme,
    device_scale_factor, and extra HTTP headers for Sec-CH-UA.
    """
    options: Dict[str, Any] = {
        "user_agent": fp.user_agent,
        "viewport": {"width": fp.viewport_width, "height": fp.viewport_height},
        "device_scale_factor": fp.device_scale_factor,
        "locale": fp.locale,
        "timezone_id": fp.timezone,
        "color_scheme": random.choice(["light", "dark", "no-preference"]),
        "reduced_motion": random.choice(["reduce", "no-preference"]),
        "has_touch": fp.max_touch_points > 0,
    }

    # Build extra HTTP headers
    extra_headers: Dict[str, str] = {}
    if fp.sec_ch_ua:
        extra_headers["sec-ch-ua"] = fp.sec_ch_ua
        extra_headers["sec-ch-ua-mobile"] = fp.sec_ch_ua_mobile
        extra_headers["sec-ch-ua-platform"] = fp.sec_ch_ua_platform

    if fp.do_not_track:
        extra_headers["DNT"] = fp.do_not_track

    # Accept-Language header from languages list
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
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-scrollbars",
        "--mute-audio",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=IsolateOrigins,site-per-process,TranslateUI",
        "--disable-ipc-flooding-protection",
        "--no-sandbox",
    ]


# ─── Convenience wrapper ─────────────────────────────────────────────────────

def apply_fingerprint_to_context(
    context,
    fp: BrowserFingerprint,
) -> None:
    """Apply the fingerprint injection script to an already-created Playwright context.
    
    Call this BEFORE navigating to any page.
    
    Args:
        context: A Playwright BrowserContext instance.
        fp: The BrowserFingerprint to inject.
    """
    import asyncio
    script = get_injection_script(fp)
    # add_init_script can be sync on the context
    if asyncio.iscoroutinefunction(getattr(context, 'add_init_script', None)):
        # Will need to be awaited by the caller
        return context.add_init_script(script)
    else:
        context.add_init_script(script)
