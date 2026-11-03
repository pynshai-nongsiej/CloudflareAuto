"""Direct Playwright automation for TenBox Websurfer registration & OTP verification.

Handles the referral link flow:
  referral page → login → email entry → Send OTP → OTP page → verify → dashboard

All sessions use a fully randomized browser fingerprint for anti-detection.
"""

import asyncio
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, BrowserContext
from .tempmail_client import TempMailClient
from .referrers import get_random_referrer
from .fingerprint import (
    generate_fingerprint,
    get_injection_script,
    get_playwright_context_options,
    get_launch_args,
    BrowserFingerprint,
)

# Load .env if present
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass


def resolve_playwright_proxy(
    proxy_arg: Optional[Union[str, dict]] = None,
    worker_id: Optional[str] = None,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve Playwright proxy configuration dictionary with automatic residential rotation.

    Hierarchy:
      -1. If proxy_arg is already a resolved dict, return it directly.
      0. Explicit disable via proxy_arg='none'/'off' or NETWORK_MODE='vpn'/'nordvpn' or USE_PROXY='0'/'false'
      1. Explicit CLI argument --proxy
      2. Environment variable PROXY_SERVER (e.g. http://user:pass@host:port or http://host:port)
      3. Environment variables PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS
      4. Default to DataImpulse credentials if configured and not explicitly disabled.
    """
    if isinstance(proxy_arg, dict):
        return proxy_arg

    # Check if proxy is explicitly disabled (e.g. for NordVPN or direct connection)
    if (
        (proxy_arg and str(proxy_arg).strip().lower() in ("none", "off", "no", "false", "0", "disabled", "direct"))
        or os.environ.get("NETWORK_MODE", "").strip().lower() in ("vpn", "nordvpn", "direct", "none", "off")
        or os.environ.get("USE_PROXY", "").strip().lower() in ("0", "false", "no", "off")
        or os.environ.get("NO_PROXY_OVERRIDE", "").strip().lower() in ("1", "true", "yes")
    ):
        if log_fn:
            log_fn("[*] 🌐 Network Mode: Direct / NordVPN (No Proxy). Routing traffic via host network interface.")
        return None

    from src.automation.ip_tracker import acquire_fresh_residential_proxy

    raw_proxy = proxy_arg if (isinstance(proxy_arg, str) and proxy_arg) else os.environ.get("PROXY_SERVER")
    proxy_info = acquire_fresh_residential_proxy(raw_proxy=raw_proxy, worker_id=worker_id, log_fn=log_fn)
    if not proxy_info:
        return None

    proxy_cfg = {
        "server": proxy_info["server"],
        "username": proxy_info["username"],
        "password": proxy_info["password"],
        "verified_ip": proxy_info.get("verified_ip"),
        "session_id": proxy_info.get("session_id"),
    }
    return proxy_cfg

TARGET_URL = (
    "https://websurfer.1024tenbox.com/referral/XUMZDQ5R"
    if sys.platform == "win32"
    else "https://websurfer.1024tenbox.com/referral/XWUPKX2D"
)


class RateLimitError(Exception):
    """Raised when TenBox rate limits verification code requests."""
    def __init__(self, wait_seconds: int, message: str):
        super().__init__(message)
        self.wait_seconds = wait_seconds
        self.message = message


class OtpMaintenanceError(Exception):
    """Raised when TenBox displays an OTP login maintenance error."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


async def _human_click(page: Page, element_or_selector: Any, log: Optional[Callable] = None) -> None:
    """Move mouse to element using an organic human path with micro-jitter before clicking.
    Emits natural mousemove, pointerdown, and pointerup events to defeat anti-bot heuristics.
    """
    try:
        elem = element_or_selector
        if isinstance(element_or_selector, str):
            elem = await page.wait_for_selector(element_or_selector, timeout=8000, state="visible")
        if not elem:
            return

        box = await elem.bounding_box()
        if not box or box["width"] <= 0 or box["height"] <= 0:
            await elem.click()
            return

        # Target a random natural spot inside element (avoid robotic dead-center clicks)
        target_x = box["x"] + box["width"] * random.uniform(0.25, 0.75)
        target_y = box["y"] + box["height"] * random.uniform(0.30, 0.70)

        # Move mouse across interpolated steps
        steps = random.randint(10, 22)
        await page.mouse.move(target_x, target_y, steps=steps)
        await asyncio.sleep(random.uniform(0.04, 0.12))
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.12))  # realistic button-down duration
        await page.mouse.up()
    except Exception:
        try:
            if hasattr(element_or_selector, "click"):
                await element_or_selector.click()
        except Exception:
            pass


async def _human_type(page: Page, selector_or_element, text: str, log: Callable):
    """Type text with randomized delays and micro-pauses to mimic human typing."""
    element = selector_or_element
    if isinstance(selector_or_element, str):
        element = await page.wait_for_selector(selector_or_element, timeout=10000)

    await _human_click(page, element, log)
    await asyncio.sleep(random.uniform(0.15, 0.35))

    for idx, char in enumerate(text):
        delay = random.randint(35, 110)
        # Slower on special characters (@, .) like a real human searching for the key
        if char in ("@", ".", "-", "_"):
            delay += random.randint(40, 90)
        await page.keyboard.type(char, delay=delay)
        # Occasional micro-pause between typing chunks
        if idx > 0 and idx % random.randint(3, 5) == 0 and random.random() < 0.25:
            await asyncio.sleep(random.uniform(0.08, 0.22))


async def _wait_for_email_input(page: Page, timeout: int = 25000) -> Any:
    """Wait for the email input to appear, trying multiple selectors and self-healing if stuck."""
    selector_str = (
        'input[type="email"], '
        'input[name="email"], '
        'input[placeholder*="@"], '
        'input[placeholder*="email" i], '
        'input[placeholder*="Email" i], '
        'input[autocomplete="email"]'
    )

    # 1. Fast path: Wait for standard email input
    try:
        el = await page.wait_for_selector(selector_str, timeout=min(timeout // 2, 10000), state="visible")
        if el and await el.is_visible():
            return el
    except Exception:
        pass

    # 2. Self-healing: if still on /referral/ page, navigate to login page with referral code
    if "/referral/" in page.url or "/login" not in page.url:
        import re
        code_match = re.search(r'/referral/([a-zA-Z0-9_-]+)', page.url)
        code = code_match.group(1) if code_match else "XWUPKX2D"
        target_login = f"https://websurfer.1024tenbox.com/login?referralCode={code}"
        try:
            await page.goto(target_login, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1.0)
            el = await page.wait_for_selector(selector_str, timeout=12000, state="visible")
            if el and await el.is_visible():
                return el
        except Exception:
            pass

    # 3. Fallback: Any visible text/email input on the page
    inputs = await page.query_selector_all('input[type="text"], input[type="email"], input:not([type])')
    for inp in inputs:
        if await inp.is_visible():
            return inp

    # 4. Final attempt
    try:
        el = await page.wait_for_selector('input', timeout=5000, state="visible")
        if el and await el.is_visible():
            return el
    except Exception:
        pass

    raise TimeoutError(f"Could not find email input field on the page (current URL: {page.url})")


async def _find_send_otp_button(page: Page) -> Any:
    """Find the Send OTP / Submit button with multiple strategies."""
    # Strategy 1: Button with OTP-related text
    button_selectors = [
        'button:has-text("Send OTP")',
        'button:has-text("Send Code")',
        'button:has-text("Get OTP")',
        'button:has-text("Continue")',
        'button:has-text("Submit")',
        'button:has-text("Sign")',
        'button:has-text("Log")',
        'button[type="submit"]',
    ]

    for selector in button_selectors:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible() and await btn.is_enabled():
                return btn
        except Exception:
            continue

    # Strategy 2: Any visible, enabled button inside a form
    forms = await page.query_selector_all('form')
    for form in forms:
        buttons = await form.query_selector_all('button')
        for btn in buttons:
            if await btn.is_visible() and await btn.is_enabled():
                return btn

    raise TimeoutError("Could not find Send OTP / submit button")


async def _find_otp_inputs(page: Page) -> list:
    """Find OTP digit input fields."""
    # Strategy 1: Numeric inputs with maxlength=1
    inputs = await page.query_selector_all('input[maxlength="1"]')
    visible = [i for i in inputs if await i.is_visible()]
    if len(visible) >= 4:
        return visible

    # Strategy 2: Inputs with inputmode="numeric"
    inputs = await page.query_selector_all('input[inputmode="numeric"]')
    visible = [i for i in inputs if await i.is_visible()]
    if len(visible) >= 4:
        return visible

    # Strategy 3: Inputs with type="tel" or type="number" with single char
    inputs = await page.query_selector_all('input[type="tel"], input[type="number"]')
    visible = [i for i in inputs if await i.is_visible()]
    if len(visible) >= 4:
        return visible

    # Strategy 4: All visible inputs on the OTP page (exclude hidden/password)
    all_inputs = await page.query_selector_all('input:not([type="hidden"]):not([type="password"])')
    visible = [i for i in all_inputs if await i.is_visible()]
    return visible


async def _check_rate_limit_error(page: Page, intercepted: Optional[list] = None) -> Optional[Tuple[int, str]]:
    """Checks if a rate-limit error banner is displayed on the TenBox page or received over network.

    Returns (wait_seconds, full_message) if detected, else None.
    """
    if intercepted and intercepted[0]:
        return intercepted[0]

    try:
        # Check text content of visible containers / alerts
        selectors = [
            '[role="alert"]',
            '.alert',
            '.error',
            '.warning',
            '.toast',
            '.message',
            'div',
            'p',
            'span',
        ]
        text_content = ""
        rate_keywords = [
            "too many",
            "please wait",
            "try again in",
            "try again later",
            "rate limit",
            "too frequently",
            "request limit",
            "slow down",
            "cooldown",
        ]

        for sel in selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    if not await el.is_visible():
                        continue
                    txt = (await el.inner_text()).strip()
                    lower_txt = txt.lower()
                    if any(k in lower_txt for k in rate_keywords):
                        text_content = txt
                        break
                if text_content:
                    break
            except Exception:
                continue

        if not text_content:
            # Fallback check entire page body text
            body_txt = await page.evaluate("() => document.body ? document.body.innerText : ''")
            lower_body = body_txt.lower()
            if any(k in lower_body for k in rate_keywords):
                for line in body_txt.splitlines():
                    if any(k in line.lower() for k in rate_keywords):
                        text_content += (" " + line.strip()).strip()

        if text_content:
            lower_content = text_content.lower()
            if any(k in lower_content for k in rate_keywords):
                wait_seconds = 0
                # Look for "Try again in 12:19" or "12:19"
                match_mm_ss = re.search(r'(?:Try again in|wait[^\d]*)?(\d+):(\d+)', text_content, re.IGNORECASE)
                if match_mm_ss:
                    mins = int(match_mm_ss.group(1))
                    secs = int(match_mm_ss.group(2))
                    wait_seconds = mins * 60 + secs
                else:
                    match_mins = re.search(r'(\d+)\s*(?:min|minute)', text_content, re.IGNORECASE)
                    if match_mins:
                        wait_seconds = int(match_mins.group(1)) * 60
                    else:
                        match_secs = re.search(r'(\d+)\s*(?:sec|second)', text_content, re.IGNORECASE)
                        if match_secs:
                            wait_seconds = int(match_secs.group(1))

                # If wait_seconds was not found in message, default to 15-minute cooldown
                if wait_seconds <= 0:
                    wait_seconds = 900

                return (wait_seconds, text_content)
    except Exception:
        pass
    return None


async def _check_maintenance_error(page: Page, intercepted: Optional[list] = None) -> Optional[str]:
    """Checks if an OTP login maintenance error is displayed on the page or intercepted over network.

    Returns the maintenance error message if detected, otherwise None.
    """
    if intercepted and intercepted[0]:
        msg = intercepted[0]
        intercepted[0] = None
        return str(msg)

    try:
        selectors = [
            '[role="alert"]',
            '.alert',
            '.error',
            '.warning',
            '.toast',
            '.notification',
            '.message',
            '[class*="error" i]',
            '[class*="toast" i]',
            '[class*="alert" i]',
            '[class*="notice" i]',
            '[id*="error" i]',
            '[id*="toast" i]',
            'div',
            'p',
            'span',
        ]

        def _is_maintenance(text: str) -> bool:
            lower = text.lower()
            if ("maintainance" in lower or "maintenance" in lower) and ("otp" in lower or "login" in lower or "code" in lower):
                return True
            if "couldn't send the code" in lower or "please use google login" in lower:
                return True
            return False

        for sel in selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    if not await el.is_visible():
                        continue
                    txt = (await el.inner_text()).strip()
                    if txt and _is_maintenance(txt):
                        return txt
            except Exception:
                continue

        body_txt = await page.evaluate("() => document.body ? document.body.innerText : ''")
        if body_txt and _is_maintenance(body_txt):
            for line in body_txt.splitlines():
                line_str = line.strip()
                if line_str and _is_maintenance(line_str):
                    return line_str
            return "OTP login maintenance detected"
    except Exception:
        pass
    return None


async def _click_change_email(page: Page, log: Callable) -> bool:
    """Finds and clicks the 'Change Email' button/link on the OTP screen."""
    log("[*] Looking for 'Change Email' button/link on the OTP screen...")

    selectors = [
        'button:has-text("Change email")',
        'button:has-text("Change Email")',
        'button:has-text("change email")',
        'a:has-text("Change email")',
        'a:has-text("Change Email")',
        'a:has-text("change email")',
        '[role="button"]:has-text("Change email")',
        '[role="button"]:has-text("Change Email")',
        'span:has-text("Change email")',
        'span:has-text("Change Email")',
        'p:has-text("Change email")',
        'button:has-text("Change")',
        'a:has-text("Change")',
        '[role="button"]:has-text("Change")',
        'button:has-text("Edit email")',
        'a:has-text("Edit email")',
        'button:has-text("Edit")',
        'a:has-text("Edit")',
        'button:has-text("Wrong email")',
        'a:has-text("Wrong email")',
        '[aria-label*="change email" i]',
        '[aria-label*="change" i]',
        '[aria-label*="edit" i]',
        '[title*="change email" i]',
        '[title*="change" i]',
        '[title*="edit" i]',
        '[class*="change-email" i]',
        '[class*="changeEmail" i]',
        '[id*="change-email" i]',
        '[id*="changeEmail" i]',
    ]

    for sel in selectors:
        try:
            elem = await page.query_selector(sel)
            if elem and await elem.is_visible():
                txt = (await elem.inner_text()).strip()
                log(f"[+] Found Change Email element ({sel}: '{txt}'). Clicking...")
                await elem.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.2, 0.4))
                await _human_click(page, elem, log)
                return True
        except Exception:
            continue

    try:
        clicked = await page.evaluate("""() => {
            const elements = Array.from(document.querySelectorAll('button, a, span, p, div, [role="button"]'));
            for (const el of elements) {
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                if (text === 'change email' || text === 'change email address' || text === 'edit email' || text === 'change') {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        el.click();
                        return true;
                    }
                }
            }
            for (const el of elements) {
                if (el.tagName === 'BUTTON' || el.tagName === 'A' || el.getAttribute('role') === 'button' || el.onclick) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (text.includes('change email') || text.includes('change') || text.includes('edit')) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
            }
            return false;
        }""")
        if clicked:
            log("[+] Clicked 'Change Email' via DOM element search.")
            return True
    except Exception as e:
        log(f"[!] DOM evaluate for change email: {e}")

    back_selectors = [
        'button:has-text("Back")',
        'a:has-text("Back")',
        '[aria-label*="back" i]',
        '[title*="back" i]',
        '[class*="back" i]',
    ]
    for sel in back_selectors:
        try:
            elem = await page.query_selector(sel)
            if elem and await elem.is_visible():
                log(f"[+] Found Back element ({sel}). Clicking to return to email screen...")
                await _human_click(page, elem, log)
                return True
        except Exception:
            continue

    log("[!] Could not locate 'Change Email' element on OTP screen.")
    return False


async def _handle_otp_maintenance_resend(
    page: Page,
    email_address: str,
    log: Callable,
    rate_limit_intercepted: Optional[list] = None,
) -> bool:
    """Handles 'otp login maintenance' error on OTP screen:

    1. Clicks 'Change Email'.
    2. Waits for email input on the login screen.
    3. Confirms/re-fills the exact same email address.
    4. Clicks 'Send OTP' again.
    5. Waits for OTP verification screen to reload.
    """
    log(f"[*] 🔄 Triggering OTP Maintenance Recovery: Resending OTP to same email ({email_address})...")

    # Step 1: Click Change Email
    clicked = await _click_change_email(page, log)
    await asyncio.sleep(1.0)

    if not clicked or "/otp" in page.url:
        try:
            email_inp = await page.query_selector('input[type="email"], input[name="email"], input[placeholder*="@"]')
            if not email_inp or not await email_inp.is_visible():
                log("[*] Trying page.go_back() to return to login email form...")
                await page.go_back(wait_until="domcontentloaded", timeout=5000)
                await asyncio.sleep(1.0)
        except Exception:
            pass

    # Step 2: Wait for email input field to be ready
    try:
        email_input = await _wait_for_email_input(page, timeout=15000)
    except Exception as e:
        log(f"[!] Failed to find email input field after clicking Change Email: {e}")
        return False

    # Step 3: Ensure the email input field has the exact same email address
    try:
        curr_val = (await email_input.input_value()).strip()
    except Exception:
        curr_val = ""

    if curr_val.lower() != email_address.lower():
        log(f"[*] Re-filling exact same email address into input: {email_address}...")
        try:
            await email_input.click()
            select_all_key = "Meta+a" if sys.platform == "darwin" else "Control+a"
            await page.keyboard.press(select_all_key)
            await page.keyboard.press("Backspace")
            await email_input.fill("")
        except Exception:
            pass
        await asyncio.sleep(0.2)
        await _human_type(page, email_input, email_address, log)
    else:
        log(f"[+] Email input already contains exact email: {email_address}")

    await asyncio.sleep(random.uniform(0.5, 1.2))

    # Step 4: Click Send OTP button again
    try:
        send_btn = await _find_send_otp_button(page)
        log("[*] Clicking 'Send OTP' button again...")
        await _human_click(page, send_btn, log)
    except Exception as e:
        log(f"[!] Could not click Send OTP button on retry: {e}")
        return False

    # Step 5: Wait for OTP screen to reload
    log("[*] Waiting for OTP verification screen to reappear...")
    reloaded_otp = False
    start_wait = time.time()
    while (time.time() - start_wait) < 30:
        rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
        if rate_limit:
            wait_sec, msg = rate_limit
            await _take_screenshot(page, "rate_limited", log)
            raise RateLimitError(wait_sec, msg)

        if "/otp" in page.url:
            reloaded_otp = True
            break
        otp_inputs = await _find_otp_inputs(page)
        if len(otp_inputs) >= 4:
            reloaded_otp = True
            break
        await asyncio.sleep(1.0)

    if reloaded_otp:
        log("[+] ✅ Successfully returned to OTP verification screen with fresh OTP requested!")
        await asyncio.sleep(1.0)
        return True
    else:
        log(f"[!] Warning: Did not detect OTP screen within 30s of resend. Current URL: {page.url}")
        return False


async def _enter_and_verify_otp(page: Page, otp_code: str, log: Callable) -> None:
    """Enter OTP digits into fields and click verify/confirm button."""
    otp_inputs = await _find_otp_inputs(page)
    log(f"[*] Found {len(otp_inputs)} OTP input(s)")

    if len(otp_inputs) == len(otp_code):
        log(f"[*] Entering {len(otp_code)} digits individually...")
        for idx, digit in enumerate(otp_code):
            await otp_inputs[idx].fill(digit)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    elif len(otp_inputs) == 1:
        log("[*] Entering OTP into single input field...")
        await otp_inputs[0].fill(otp_code)
    else:
        log("[*] Typing OTP via keyboard...")
        if otp_inputs:
            await otp_inputs[0].focus()
        await page.keyboard.type(otp_code, delay=random.randint(40, 80))

    log("[*] Checking for verify button...")
    await asyncio.sleep(0.5)
    try:
        verify_selectors = [
            'button:has-text("Verify")',
            'button:has-text("Confirm")',
            'button:has-text("Submit")',
            'button[type="submit"]',
        ]
        for sel in verify_selectors:
            try:
                verify_btn = await page.query_selector(sel)
                if verify_btn and await verify_btn.is_visible() and await verify_btn.is_enabled():
                    log(f"[*] Clicking verify button ({sel})...")
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    await _human_click(page, verify_btn, log)
                    break
            except Exception:
                continue
    except Exception:
        pass


def cleanup_all_screenshots() -> None:
    """Remove any leftover debug screenshots from temp directory to prevent clogging storage."""
    import tempfile
    import shutil
    from pathlib import Path

    try:
        screenshot_dir = Path(tempfile.gettempdir()) / "websurfer_screenshots"
        if screenshot_dir.exists():
            shutil.rmtree(screenshot_dir, ignore_errors=True)
    except Exception:
        pass


async def _take_screenshot(page: Page, label: str, log: Callable, save: bool = False) -> Optional[str]:
    """Take a debug screenshot only if explicitly requested, otherwise avoid clogging disk."""
    if not save:
        return None

    import time
    import tempfile
    from pathlib import Path

    try:
        screenshot_dir = Path(tempfile.gettempdir()) / "websurfer_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = str(screenshot_dir / f"websurfer_{label}_{int(time.time())}.png")
        await page.screenshot(path=path)
        log(f"[!] Screenshot saved: {path}")
        return path
    except Exception:
        return None


async def register_and_verify(
    client: Optional[TempMailClient] = None,
    headed: bool = False,
    timeout: int = 90,
    cleanup_inbox: bool = False,
    log_fn: Optional[Callable[[str], None]] = None,
    target_url: Optional[str] = None,
    referrer: Optional[str] = "random",
    save_screenshots: bool = False,
    proxy: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Automates registration and OTP verification on TenBox Websurfer.
    Screenshots are disabled by default and cleaned up automatically to avoid clogging storage.

    Returns:
        dict with success status, email, otp, final URL, cookies, referrer, and storage data.
    """
    url = target_url or TARGET_URL
    def log(msg: str):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    mail_client = client or TempMailClient()

    # ── Step 0: Inbound Referrer & Fingerprint Simulation ──
    ref_info = None
    if referrer and str(referrer).lower() not in ("none", "false", "off", "direct", "empty"):
        preferred = None if str(referrer).lower() in ("random", "auto") else str(referrer).lower()
        ref_info = get_random_referrer(url, preferred_platform=preferred)
        log(f"[*] 🌐 Inbound Referrer Simulated: {ref_info['platform']} -> {ref_info['url'][:70]}...")

    host_platform = {"darwin": "darwin", "win32": "win32", "linux": "linux"}.get(sys.platform, None)
    fp = generate_fingerprint(prefer_platform=host_platform)
    log(f"[*] Fingerprint: UA={fp.user_agent[:60]}...")
    log(f"    OS={fp.platform_name} ({fp.platform}) | GPU={fp.webgl_renderer[:35]}...")
    log(f"    Screen={fp.screen_width}x{fp.screen_height} | Viewport={fp.viewport_width}x{fp.viewport_height} | "
        f"Scale={fp.device_scale_factor}")

    # Check for proxy configuration (explicit CLI argument, environment, or DataImpulse)
    proxy_config = resolve_playwright_proxy(proxy, worker_id, log)
    is_proxy_active = bool(proxy_config)

    assigned_ip = proxy_config.get("verified_ip") if proxy_config else None
    if assigned_ip:
        log(f"[+] 🌐 Starting Chromium on verified residential IP: {assigned_ip} (Session: {proxy_config.get('session_id')})")
    elif not is_proxy_active:
        log("[*] 🌐 Starting Chromium on direct device network (No Proxy)")

    pw_proxy = None
    if proxy_config:
        pw_proxy = {
            "server": proxy_config["server"],
            "username": proxy_config["username"],
            "password": proxy_config["password"],
        }

    # ── Step 1: Create temporary email (TempMail.Plus random name & domain) ──
    log("[*] Creating temporary email on TempMail.Plus...")
    inbox = mail_client.create_inbox()
    email_address = inbox["address"]
    local_part = inbox.get("name", email_address.split("@")[0])
    log(f"[+] Inbox ready: {email_address} (domain: @{inbox.get('domain', '')})")

    async with async_playwright() as p:
        # ── Step 2: Launch browser with stealth config ──
        launch_kwargs = {
            "headless": not headed,
            "args": get_launch_args(),
        }
        if pw_proxy:
            launch_kwargs["proxy"] = pw_proxy

        log(f"[*] Launching Chromium (headed={headed}) with stealth fingerprint...")
        browser = await p.chromium.launch(**launch_kwargs)

        context_opts = get_playwright_context_options(fp)
        if pw_proxy:
            context_opts["proxy"] = pw_proxy
        if ref_info:
            extra_h = context_opts.get("extra_http_headers", {})
            extra_h["Sec-Fetch-Site"] = "cross-site"
            extra_h["Sec-Fetch-Mode"] = "navigate"
            extra_h["Sec-Fetch-Dest"] = "document"
            context_opts["extra_http_headers"] = extra_h

        context = await browser.new_context(**context_opts)
        await context.add_init_script(get_injection_script(fp))

        if ref_info:
            ref_script = f"""
            (() => {{
                try {{
                    Object.defineProperty(document, 'referrer', {{
                        get: () => {json.dumps(ref_info['url'])},
                        configurable: true
                    }});
                }} catch(e) {{}}
            }})();
            """
            await context.add_init_script(ref_script)

        page = await context.new_page()

        # ── Data-saver: Block heavy resource types that are not needed for automation ──
        # Images, fonts, media, and stylesheets account for the vast majority of page
        # bandwidth. The SPA's login/OTP flow relies only on JS, XHR/fetch, and the
        # HTML document itself — blocking everything else is safe.
        _BLOCKED_TYPES = {
            "image", "imageset", "media", "font",
            "stylesheet", "texttrack", "eventsource",
            "websocket", "manifest", "other",
        }
        # Also block third-party analytics / tracking / CDN ad domains
        _BLOCKED_DOMAINS = {
            "google-analytics.com", "googletagmanager.com", "doubleclick.net",
            "facebook.net", "facebook.com/tr", "hotjar.com", "intercom.io",
            "segment.com", "amplitude.com", "mixpanel.com", "fullstory.com",
            "clarity.ms", "nr-data.net", "newrelic.com", "sentry.io",
        }

        async def _block_unnecessary_resources(route):
            req = route.request
            rtype = req.resource_type  # e.g. "image", "stylesheet", "font", ...
            if rtype in _BLOCKED_TYPES:
                await route.abort()
                return
            url_lower = req.url.lower()
            if any(domain in url_lower for domain in _BLOCKED_DOMAINS):
                await route.abort()
                return
            await route.continue_()

        await page.route("**/*", _block_unnecessary_resources)

        # Monitor network responses for HTTP 429 rate limit or maintenance
        rate_limit_intercepted = [None]
        maintenance_intercepted = [None]

        def _on_response(resp):
            if resp.status == 429:
                rate_limit_intercepted[0] = (900, f"HTTP 429 Too Many Requests from {resp.url}")

        page.on("response", _on_response)

        try:
            # ── Step 3: Navigate to referral URL with retry logic ──
            ref_label = f" (referrer: {ref_info['platform']})" if ref_info else ""
            log(f"[*] Navigating to {url}{ref_label}...")
            max_nav_retries = 3
            nav_success = False
            last_nav_err = None

            for attempt in range(1, max_nav_retries + 1):
                try:
                    if attempt > 1:
                        log(f"[*] Retrying navigation (attempt {attempt}/{max_nav_retries})...")
                    # Try domcontentloaded first, fallback to commit if server takes time to deliver full DOM
                    wait_until_strategy = "domcontentloaded" if attempt <= 2 else "commit"
                    goto_kwargs = {"wait_until": wait_until_strategy, "timeout": 30000}
                    if ref_info:
                        goto_kwargs["referer"] = ref_info["url"]

                    await page.goto(url, **goto_kwargs)
                    nav_success = True
                    break
                except Exception as nav_err:
                    last_nav_err = nav_err
                    log(f"[!] Navigation attempt {attempt} failed: {nav_err}")
                    if attempt < max_nav_retries:
                        await asyncio.sleep(attempt * 2)

            if not nav_success:
                raise TimeoutError(
                    f"Failed to reach {url} after {max_nav_retries} attempts: {last_nav_err}\n"
                    f"Check your internet connection or whether {url} is currently reachable from your network/VPN."
                )

            # Wait for the SPA to initialize and simulate realistic human browsing
            await asyncio.sleep(2)
            current_url = page.url
            log(f"[*] Page loaded, current URL: {current_url}")


            # Determine canonical login URL from referral code
            ref_code = None
            code_m = re.search(r'/referral/([a-zA-Z0-9_-]+)', url)
            if code_m:
                ref_code = code_m.group(1)
            elif "referralCode=" in url:
                code_m = re.search(r'referralCode=([a-zA-Z0-9_-]+)', url)
                if code_m:
                    ref_code = code_m.group(1)

            canonical_login_url = (
                f"https://websurfer.1024tenbox.com/login?referralCode={ref_code}"
                if ref_code
                else "https://websurfer.1024tenbox.com/login"
            )

            # If not already on /login, try clicking CTA button or fallback directly to canonical login
            if "/login" not in page.url:
                cta_clicked = False
                cta_selectors = [
                    'a:has-text("Get started free")',
                    'button:has-text("Get started free")',
                    'a[href*="login"]',
                    'a:has-text("Get started")',
                    'button:has-text("Get started")',
                    'a:has-text("Sign up")',
                    'button:has-text("Sign up")',
                    'a:has-text("Join")',
                    'button:has-text("Join")',
                    'a:has-text("Start")',
                ]

                for sel in cta_selectors:
                    try:
                        btn = await page.wait_for_selector(sel, timeout=3000, state="visible")
                        if btn:
                            log(f"[*] Found CTA button, clicking: {sel}")
                            await asyncio.sleep(random.uniform(0.5, 1.2))
                            await _human_click(page, btn, log)
                            cta_clicked = True
                            break
                    except Exception:
                        continue

                # Check if login form appeared after CTA click
                login_form_ready = False
                try:
                    await page.wait_for_selector(
                        'input[type="email"], input[name="email"], input[placeholder*="@"]',
                        timeout=5000,
                        state="visible"
                    )
                    login_form_ready = True
                    log(f"[+] Login form ready at: {page.url}")
                except Exception:
                    pass

                # FAILSAFE for Linux / slow SPAs: If CTA didn't transition, navigate directly to login URL
                if not login_form_ready or "/login" not in page.url:
                    log(f"[*] Navigating directly to login page: {canonical_login_url}")
                    try:
                        await page.goto(canonical_login_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_selector(
                            'input[type="email"], input[name="email"], input[placeholder*="@"]',
                            timeout=15000,
                            state="visible"
                        )
                        log(f"[+] Login form ready at: {page.url}")
                    except Exception as nav_e:
                        await _take_screenshot(page, "login_load_failed", log)
                        log(f"[!] Login form load warning: {nav_e}")

            # Check if page is already showing a rate limit error banner
            initial_rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
            if initial_rate_limit:
                wait_sec, msg = initial_rate_limit
                await _take_screenshot(page, "rate_limited_initial", log)
                log(f"[!] ⚠️ Form is already rate-limited by TenBox: {msg}")
                raise RateLimitError(wait_sec, msg)

            # ── Step 4: Enter email ──
            log(f"[*] Looking for email input field...")
            email_input = await _wait_for_email_input(page)
            log(f"[*] Found email input, entering: {email_address}")

            # Clear any existing content first (Linux uses Control+a, macOS uses Meta+a)
            await _human_click(page, email_input, log)
            select_all_key = "Meta+a" if sys.platform == "darwin" else "Control+a"
            await page.keyboard.press(select_all_key)
            await page.keyboard.press("Backspace")
            try:
                await email_input.fill("")
            except Exception:
                pass
            await asyncio.sleep(0.2)

            # Type like a human
            await _human_type(page, email_input, email_address, log)
            await asyncio.sleep(random.uniform(0.3, 0.8))

            # ── Step 5: Click Send OTP ──
            log("[*] Looking for Send OTP button...")
            send_btn = await _find_send_otp_button(page)
            log("[*] Clicking Send OTP...")

            # Realistic pause before submitting email (like reviewing typed email)
            await asyncio.sleep(random.uniform(1.2, 2.5))
            await _human_click(page, send_btn, log)

            # ── Step 6: Wait for OTP page ──
            log("[*] Waiting for OTP verification screen...")

            # The SPA may navigate to /otp or show OTP inputs on the same page.
            # Allow extended wait time (at least 2 minutes / 120s) for slow networks or server processing.
            otp_found = False
            max_otp_wait = max(120, int(timeout))
            start_wait = time.time()
            reclick_done = False

            while (time.time() - start_wait) < max_otp_wait:
                elapsed = int(time.time() - start_wait)

                # Check if server returned rate limit error
                rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
                if rate_limit:
                    wait_sec, msg = rate_limit
                    await _take_screenshot(page, "rate_limited", log)
                    log(f"[!] ⚠️ Rate limit encountered: {msg}")
                    raise RateLimitError(wait_sec, msg)

                # Fast check: Did URL navigate to /otp?
                if "/otp" in page.url:
                    log(f"[+] Navigated to OTP page: {page.url} (took {elapsed}s)")
                    otp_found = True
                    break

                try:
                    # Check if URL changed to /otp
                    await page.wait_for_url("**/otp**", timeout=1500)
                    log(f"[+] Navigated to OTP page: {page.url} (took {elapsed}s)")
                    otp_found = True
                    break
                except Exception:
                    pass

                # Check if maintenance error appeared on login form while still stuck on /login
                maint_early = await _check_maintenance_error(page, maintenance_intercepted)
                if maint_early and "/otp" not in page.url:
                    log(f"[!] ⚠️ OTP login maintenance detected on /login: {maint_early}")
                    raise OtpMaintenanceError(maint_early)

                # Check if OTP inputs appeared on current page
                otp_inputs = await _find_otp_inputs(page)
                if len(otp_inputs) >= 4:
                    log(f"[+] OTP inputs detected on current page ({len(otp_inputs)} fields, took {elapsed}s)")
                    otp_found = True
                    break

                # Self-healing for slow networks: if after 25s we are still on login page and Send OTP is still enabled, retry click once
                if not reclick_done and elapsed >= 25 and "/otp" not in page.url:
                    try:
                        retry_btn = await _find_send_otp_button(page)
                        if retry_btn and await retry_btn.is_visible() and await retry_btn.is_enabled():
                            log(f"[*] OTP screen not reached after {elapsed}s; re-clicking Send OTP button...")
                            await retry_btn.click()
                            reclick_done = True
                    except Exception:
                        pass

                if elapsed > 0 and elapsed % 5 == 0:
                    log(f"[*] Waiting for OTP screen to load ({elapsed}/{max_otp_wait}s)...")

                await asyncio.sleep(1)

            if not otp_found:
                # Final check for rate limit error banner
                rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
                if rate_limit:
                    wait_sec, msg = rate_limit
                    await _take_screenshot(page, "rate_limited", log)
                    log(f"[!] ⚠️ Rate limit encountered: {msg}")
                    raise RateLimitError(wait_sec, msg)

                await _take_screenshot(page, "no_otp_page", log)
                raise TimeoutError(f"OTP page/inputs not found after clicking Send OTP (waited {max_otp_wait}s). Current URL: {page.url}")

            await asyncio.sleep(1)  # Let the page settle

            # Quick check if maintenance error is immediately visible upon landing on OTP screen
            initial_maint = await _check_maintenance_error(page, maintenance_intercepted)
            if initial_maint:
                log(f"[!] ⚠️ Immediate OTP login maintenance error on OTP screen: {initial_maint}")
                raise OtpMaintenanceError(initial_maint)

            # ── Step 7: Poll for OTP code with maintenance check & auto-resend ──
            log(f"[*] Polling TempMail.Plus inbox for OTP code ({email_address})...")
            otp_timeout = max(120, timeout)
            otp_code = None
            start_poll = time.time()
            poll_attempt = 1
            maintenance_retries = 0
            max_maintenance_retries = 3

            while (time.time() - start_poll) < otp_timeout:
                # 1. Non-blocking check for OTP in TempMail.Plus inbox
                otp_code = await asyncio.to_thread(mail_client.get_latest_code, email_address)
                if otp_code:
                    log(f"[+] Received OTP code: {otp_code}")
                    break

                elapsed = int(time.time() - start_poll)
                if elapsed > 0 and elapsed % 6 == 0:
                    log(f"[*] Waiting for OTP on {email_address}... ({elapsed}/{otp_timeout}s elapsed, attempt {poll_attempt})")

                # 2. Check if rate limit error appeared
                rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
                if rate_limit:
                    wait_sec, msg = rate_limit
                    await _take_screenshot(page, "rate_limited", log)
                    log(f"[!] ⚠️ Rate limit encountered: {msg}")
                    raise RateLimitError(wait_sec, msg)

                # 3. Check for OTP login maintenance error on OTP screen
                maint_err = await _check_maintenance_error(page, maintenance_intercepted)
                if maint_err:
                    log(f"[!] ⚠️ OTP login maintenance detected on OTP screen: {maint_err}")
                    raise OtpMaintenanceError(maint_err)

                await asyncio.sleep(2.0)
                poll_attempt += 1

            if not otp_code:
                await _take_screenshot(page, "otp_timeout", log)
                raise TimeoutError(f"OTP code did not arrive within {otp_timeout} seconds.")

            log(f"[+] OTP received: {otp_code}")

            # ── Step 8 & 9: Enter OTP digits and submit ──
            await _enter_and_verify_otp(page, otp_code, log)

            # ── Step 10: Wait for dashboard ──
            log("[*] Waiting for dashboard redirection...")
            dashboard_reached = False
            start_dash_wait = time.time()
            dash_timeout = 25
            post_maint_handled = False

            while (time.time() - start_dash_wait) < dash_timeout:
                current = page.url
                if "/otp" not in current and "/login" not in current and "/referral" not in current:
                    dashboard_reached = True
                    break

                # Check if rate limit error banner appeared
                rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
                if rate_limit:
                    wait_sec, msg = rate_limit
                    await _take_screenshot(page, "rate_limited", log)
                    log(f"[!] ⚠️ Rate limit encountered: {msg}")
                    raise RateLimitError(wait_sec, msg)

                # Check if maintenance error appeared after submitting OTP
                maint_err = await _check_maintenance_error(page, maintenance_intercepted)
                if maint_err:
                    log(f"[!] ⚠️ OTP login maintenance detected after OTP submission: {maint_err}")
                    raise OtpMaintenanceError(maint_err)

                await asyncio.sleep(1.0)

            if not dashboard_reached:
                current = page.url
                if "/otp" not in current and "/login" not in current:
                    log(f"[*] Already on dashboard: {current}")
                else:
                    await _take_screenshot(page, "no_dashboard", log)
                    raise TimeoutError(f"Dashboard not reached. Current URL: {current}")

            await asyncio.sleep(2)  # Let SPA settle

            final_url = page.url
            log(f"[+] ✅ Successfully verified! Dashboard: {final_url}")

            # ── Step 11: Collect session data ──
            body_text = await page.inner_text("body")
            preview = "\n".join([line for line in body_text.splitlines() if line.strip()][:10])

            cookies = await context.cookies()
            storage_data = await page.evaluate("""() => {
                return {
                    localStorage: { ...localStorage },
                    sessionStorage: { ...sessionStorage }
                };
            }""")

            result = {
                "success": True,
                "email": email_address,
                "otp": otp_code,
                "url": final_url,
                "cookies": cookies,
                "auth_storage": storage_data,
                "preview": preview,
                "fingerprint": {
                    "user_agent": fp.user_agent,
                    "platform": fp.platform,
                    "viewport": f"{fp.viewport_width}x{fp.viewport_height}",
                    "timezone": fp.timezone,
                    "webgl_renderer": fp.webgl_renderer,
                },
                "referrer": ref_info,
            }

            if cleanup_inbox:
                log("[*] Cleaning up temporary inbox on TempMail.Plus...")
                mail_client.delete_inbox(email_address)

            return result

        except Exception as e:
            log(f"[-] Error during registration/verification: {e}")
            await _take_screenshot(page, "error", log)
            raise
        finally:
            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
            # Always delete any debug screenshots to prevent clogging storage
            cleanup_all_screenshots()
