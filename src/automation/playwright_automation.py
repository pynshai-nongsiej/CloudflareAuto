"""Direct Playwright automation for TenBox Websurfer registration & OTP verification.

Handles the referral link flow:
  referral page → login → email entry → Send OTP → OTP page → verify → dashboard

All sessions use a fully randomized browser fingerprint for anti-detection.
"""

import asyncio
import random
import re
import sys
from typing import Any, Callable, Dict, Optional, Tuple

from playwright.async_api import async_playwright, Page, BrowserContext
from .tempmail_client import TempMailClient
from .fingerprint import (
    generate_fingerprint,
    get_injection_script,
    get_playwright_context_options,
    get_launch_args,
    BrowserFingerprint,
)

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


async def _human_type(page: Page, selector_or_element, text: str, log: Callable):
    """Type text with randomized delays to mimic human input."""
    element = selector_or_element
    if isinstance(selector_or_element, str):
        element = await page.wait_for_selector(selector_or_element, timeout=10000)

    await element.click()
    await asyncio.sleep(random.uniform(0.1, 0.3))

    for char in text:
        await page.keyboard.type(char, delay=random.randint(30, 120))
        # Occasional micro-pause between characters
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.1, 0.3))


async def _wait_for_email_input(page: Page, timeout: int = 20000) -> Any:
    """Wait for the email input to appear, trying multiple selectors."""
    selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[placeholder*="@"]',
        'input[placeholder*="email" i]',
        'input[placeholder*="Email" i]',
        'input[autocomplete="email"]',
    ]

    for selector in selectors:
        try:
            el = await page.wait_for_selector(selector, timeout=timeout // len(selectors))
            if el and await el.is_visible():
                return el
        except Exception:
            continue

    # Fallback: find any visible text/email input
    inputs = await page.query_selector_all('input[type="text"], input[type="email"], input:not([type])')
    for inp in inputs:
        if await inp.is_visible():
            return inp

    raise TimeoutError("Could not find email input field on the page")


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


async def _take_screenshot(page: Page, label: str, log: Callable) -> Optional[str]:
    """Take a debug screenshot and return the path."""
    import time
    import tempfile
    from pathlib import Path
    
    screenshot_dir = Path(tempfile.gettempdir()) / "websurfer_screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    path = str(screenshot_dir / f"websurfer_{label}_{int(time.time())}.png")
    try:
        await page.screenshot(path=path)
        log(f"[!] Screenshot saved: {path}")
        return path
    except Exception:
        return None


async def register_and_verify(
    client: Optional[TempMailClient] = None,
    headed: bool = False,
    timeout: int = 60,
    cleanup_inbox: bool = False,
    log_fn: Optional[Callable[[str], None]] = None,
    target_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Automates registration and OTP verification on TenBox Websurfer.

    Flow:
    1. Generates a randomized browser fingerprint.
    2. Creates a temporary email inbox.
    3. Navigates to the referral URL (SPA routes to login form).
    4. Enters email and clicks Send OTP.
    5. Waits for OTP page, polls inbox for the verification code.
    6. Enters OTP digits and verifies dashboard redirection.

    Returns:
        dict with success status, email, otp, final URL, cookies, and storage data.
    """
    url = target_url or TARGET_URL
    def log(msg: str):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    mail_client = client or TempMailClient()

    # ── Step 0: Generate randomized fingerprint ──
    host_platform = {"darwin": "darwin", "win32": "win32", "linux": "linux"}.get(sys.platform, None)
    fp = generate_fingerprint(prefer_platform=host_platform)
    log(f"[*] Fingerprint: UA={fp.user_agent[:55]}...")
    log(f"    Platform={fp.platform} | GPU={fp.webgl_renderer[:35]}...")
    log(f"    TZ={fp.timezone} | Viewport={fp.viewport_width}x{fp.viewport_height} | "
        f"Scale={fp.device_scale_factor}")

    # ── Step 1: Create temporary email (TempMail.Plus random name & domain) ──
    log("[*] Creating temporary email on TempMail.Plus...")
    inbox = mail_client.create_inbox()
    email_address = inbox["address"]
    local_part = inbox.get("name", email_address.split("@")[0])
    log(f"[+] Inbox ready: {email_address} (domain: @{inbox.get('domain', '')})")

    async with async_playwright() as p:
        # ── Step 2: Launch browser with stealth config ──
        log(f"[*] Launching Chromium (headed={headed}) with stealth fingerprint...")
        browser = await p.chromium.launch(
            headless=not headed,
            args=get_launch_args(),
        )

        context_opts = get_playwright_context_options(fp)
        context = await browser.new_context(**context_opts)
        await context.add_init_script(get_injection_script(fp))

        page = await context.new_page()

        # Monitor network responses for HTTP 429 rate limit
        rate_limit_intercepted = [None]

        def _on_response(resp):
            if resp.status == 429:
                rate_limit_intercepted[0] = (900, f"HTTP 429 Too Many Requests from {resp.url}")

        page.on("response", _on_response)

        try:
            # ── Step 3: Navigate to referral URL with retry logic ──
            log(f"[*] Navigating to {url}...")
            max_nav_retries = 3
            nav_success = False
            last_nav_err = None

            for attempt in range(1, max_nav_retries + 1):
                try:
                    if attempt > 1:
                        log(f"[*] Retrying navigation (attempt {attempt}/{max_nav_retries})...")
                    # Try domcontentloaded first, fallback to commit if server takes time to deliver full DOM
                    wait_until_strategy = "domcontentloaded" if attempt <= 2 else "commit"
                    await page.goto(url, wait_until=wait_until_strategy, timeout=30000)
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

            # Wait for the SPA to initialize
            await asyncio.sleep(2)
            current_url = page.url
            log(f"[*] Page loaded, current URL: {current_url}")

            # The referral page is a landing page with a CTA button.
            # We need to click "Get started free" to go to the login form.
            cta_clicked = False
            cta_selectors = [
                'a:has-text("Get started free")',
                'button:has-text("Get started free")',
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
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        log(f"[*] Found CTA button, clicking: {sel}")
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        await btn.click()
                        cta_clicked = True
                        break
                except Exception:
                    continue

            if not cta_clicked:
                # Fallback: try clicking any prominent button/link on the page
                log("[*] CTA button not found by text, trying prominent links...")
                links = await page.query_selector_all('a[href*="login"], a[href*="signup"], a[href*="register"]')
                for link in links:
                    if await link.is_visible():
                        log(f"[*] Clicking link to login/signup...")
                        await link.click()
                        cta_clicked = True
                        break

            if cta_clicked:
                # Wait for navigation to login page
                log("[*] Waiting for login form to load...")
                await asyncio.sleep(2)
                try:
                    await page.wait_for_selector(
                        'input[type="email"], input[name="email"], input[placeholder*="@"]',
                        timeout=15000,
                    )
                    log(f"[+] Login form loaded at: {page.url}")
                except Exception:
                    await _take_screenshot(page, "after_cta_click", log)
                    log(f"[!] Login form not found after CTA click. URL: {page.url}")
            else:
                # Maybe we're already on the login page or the form is inline
                log("[*] No CTA found — checking if login form is already present...")
                try:
                    await page.wait_for_selector(
                        'input[type="email"], input[name="email"], input[placeholder*="@"]',
                        timeout=10000,
                    )
                    log(f"[+] Login form detected at: {page.url}")
                except Exception:
                    await _take_screenshot(page, "no_login_form", log)
                    log(f"[!] Current URL: {page.url} — attempting to find form anyway")

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

            # Clear any existing content first
            await email_input.click()
            await page.keyboard.press("Meta+a")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.2)

            # Type like a human
            await _human_type(page, email_input, email_address, log)
            await asyncio.sleep(random.uniform(0.3, 0.8))

            # ── Step 5: Click Send OTP ──
            log("[*] Looking for Send OTP button...")
            send_btn = await _find_send_otp_button(page)
            log("[*] Clicking Send OTP...")

            # Small pause before clicking (human-like)
            await asyncio.sleep(random.uniform(0.2, 0.6))
            await send_btn.click()

            # ── Step 6: Wait for OTP page ──
            log("[*] Waiting for OTP verification screen...")

            # The SPA may navigate to /otp or show OTP inputs on the same page
            otp_found = False
            for attempt in range(5):
                # Check if server returned rate limit error
                rate_limit = await _check_rate_limit_error(page, rate_limit_intercepted)
                if rate_limit:
                    wait_sec, msg = rate_limit
                    await _take_screenshot(page, "rate_limited", log)
                    log(f"[!] ⚠️ Rate limit encountered: {msg}")
                    raise RateLimitError(wait_sec, msg)

                try:
                    # Check if URL changed to /otp
                    await page.wait_for_url("**/otp**", timeout=2000)
                    log(f"[+] Navigated to OTP page: {page.url}")
                    otp_found = True
                    break
                except Exception:
                    pass

                # Check if OTP inputs appeared on current page
                otp_inputs = await _find_otp_inputs(page)
                if len(otp_inputs) >= 4:
                    log(f"[+] OTP inputs detected on current page ({len(otp_inputs)} fields)")
                    otp_found = True
                    break

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
                raise TimeoutError(f"OTP page/inputs not found after clicking Send OTP. Current URL: {page.url}")

            await asyncio.sleep(1)  # Let the page settle

            # ── Step 7: Poll for OTP code ──
            log(f"[*] Polling TempMail.Plus inbox for OTP code ({email_address})...")
            otp_code = await asyncio.to_thread(
                mail_client.wait_for_otp,
                email_address,
                timeout=timeout,
                poll_interval=2.0,
                log_callback=log,
            )

            if not otp_code:
                await _take_screenshot(page, "otp_timeout", log)
                raise TimeoutError(f"OTP code did not arrive within {timeout} seconds.")

            log(f"[+] OTP received: {otp_code}")

            # ── Step 8: Enter OTP digits ──
            otp_inputs = await _find_otp_inputs(page)
            log(f"[*] Found {len(otp_inputs)} OTP input(s)")

            if len(otp_inputs) == len(otp_code):
                # Individual digit inputs
                log(f"[*] Entering {len(otp_code)} digits individually...")
                for idx, digit in enumerate(otp_code):
                    await otp_inputs[idx].fill(digit)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
            elif len(otp_inputs) == 1:
                # Single combined input
                log("[*] Entering OTP into single input field...")
                await otp_inputs[0].fill(otp_code)
            else:
                # Fallback: focus first input and type the whole code
                log("[*] Typing OTP via keyboard...")
                if otp_inputs:
                    await otp_inputs[0].focus()
                await page.keyboard.type(otp_code, delay=random.randint(40, 80))

            # ── Step 9: Handle verify button (if not auto-submit) ──
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
                            await verify_btn.click()
                            break
                    except Exception:
                        continue
            except Exception:
                pass  # Auto-submit may have already navigated

            # ── Step 10: Wait for dashboard ──
            log("[*] Waiting for dashboard redirection...")
            try:
                await page.wait_for_url(
                    lambda u: "/otp" not in u and "/login" not in u and "/referral" not in u,
                    timeout=20000,
                )
            except Exception:
                # Check if we're already on the dashboard
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
