3"""OUO.io Bypass Automation Engine — navigates through ouo.io shortener pages to reach final destinations."""

import asyncio
import logging
import os
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from .fingerprint import (
    BrowserFingerprint,
    generate_fingerprint,
    get_stealth_script,
    get_launch_args,
    get_context_options,
)

logger = logging.getLogger(__name__)


class OUOBypassError(Exception):
    """Raised when the bypass flow fails irrecoverably."""
    pass


class OUOBypassEngine:
    """Playwright-based engine to bypass ouo.io link shortener pages.

    ouo.io flow (typical):
        1. Navigate to ouo.io/<code>
        2. Possible Cloudflare challenge page
        3. First interstitial page with form#form-go + possible countdown
        4. Submit form -> second interstitial / confirmation page
        5. Final submit -> redirect to destination URL

    The engine handles:
        - Cloudflare Turnstile challenges (waits for auto-solve)
        - Countdown timers
        - Form submissions (multiple steps)
        - Popup/new-tab interception
        - Human-like mouse movement and scrolling
    """

    def __init__(
        self,
        headless: bool = True,
        page_load_timeout: int = 60,
        form_wait_timeout: int = 30,
        challenge_wait_timeout: int = 45,
        countdown_wait: int = 15,
        action_delay_min: float = 1.5,
        action_delay_max: float = 4.0,
        destination_dwell_min: float = 7.0,
        destination_dwell_max: float = 15.0,
        scroll_steps: int = 4,
        screenshot_dir: str = "screenshots",
        take_screenshots: bool = True,
        engine_type: str = "nodriver",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.headless = headless
        self.engine_type = engine_type.lower()
        self.page_load_timeout = page_load_timeout
        self.form_wait_timeout = form_wait_timeout
        self.challenge_wait_timeout = challenge_wait_timeout
        self.countdown_wait = countdown_wait
        self.action_delay_min = action_delay_min
        self.action_delay_max = action_delay_max
        self.destination_dwell_min = max(7.0, destination_dwell_min)
        self.destination_dwell_max = destination_dwell_max
        self.scroll_steps = scroll_steps
        self.screenshot_dir = screenshot_dir
        self.take_screenshots = take_screenshots
        self.log_callback = log_callback or self._default_log

        os.makedirs(self.screenshot_dir, exist_ok=True)


    # ─── Logging ─────────────────────────────────────────────────────────────

    def _log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.log_callback(formatted)

    def _default_log(self, message: str):
        print(message)
        logger.info(message)

    # ─── Human-like Behavior ─────────────────────────────────────────────────

    async def _random_delay(self, min_s: Optional[float] = None, max_s: Optional[float] = None):
        """Sleep for a random duration to mimic human behavior."""
        lo = min_s if min_s is not None else self.action_delay_min
        hi = max_s if max_s is not None else self.action_delay_max
        delay = random.uniform(lo, hi)
        await asyncio.sleep(delay)

    async def _human_mouse_move(self, page: Page, x: int, y: int, steps: int = 0):
        """Move mouse to target position with optional intermediate steps."""
        if steps == 0:
            steps = random.randint(3, 8)
        await page.mouse.move(x, y, steps=steps)

    async def _simulate_reading(self, page: Page):
        """Simulate human-like page reading with scrolling and mouse movements."""
        try:
            viewport = page.viewport_size or {"width": 1280, "height": 800}

            for _ in range(self.scroll_steps):
                increment = random.randint(150, 400)
                await page.evaluate(f"window.scrollBy({{top: {increment}, behavior: 'smooth'}})")
                # Random mouse movement
                target_x = random.randint(100, viewport["width"] - 100)
                target_y = random.randint(100, viewport["height"] - 100)
                await self._human_mouse_move(page, target_x, target_y)
                await asyncio.sleep(random.uniform(0.5, 1.5))

            # Scroll back up a bit
            back = random.randint(100, 300)
            await page.evaluate(f"window.scrollBy({{top: -{back}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            self._log(f"  ⚠ Scroll simulation notice: {e}")

    async def _take_screenshot(self, page: Page, label: str, session_id: str):
        """Save a screenshot if screenshots are enabled."""
        if not self.take_screenshots:
            return None
        safe_label = "".join(c if c.isalnum() or c in "_-" else "_" for c in label)[:40]
        path = os.path.join(self.screenshot_dir, f"{session_id}_{safe_label}.png")
        try:
            await page.screenshot(path=path, full_page=False)
            self._log(f"  📸 Screenshot saved: {path}")
            return path
        except Exception as e:
            self._log(f"  ⚠ Screenshot failed: {e}")
            return None

    # ─── Cloudflare / Challenge Handling ─────────────────────────────────────

    async def _wait_for_challenge(self, page: Page) -> bool:
        """Detect and wait for Cloudflare Turnstile or similar challenges to auto-resolve.

        Returns True if a challenge was detected and waited on.
        """
        challenge_selectors = [
            "iframe[src*='challenges.cloudflare.com']",
            "#turnstile-wrapper iframe",
            ".cf-turnstile iframe",
            "iframe[title*='Cloudflare']",
            "#challenge-running",
            "#challenge-stage",
        ]

        for selector in challenge_selectors:
            try:
                challenge = await page.query_selector(selector)
                if challenge:
                    self._log("  🔒 Cloudflare challenge detected — waiting for auto-solve...")
                    # Wait for the challenge container to disappear or page to navigate
                    try:
                        await page.wait_for_selector(
                            selector, state="hidden", timeout=self.challenge_wait_timeout * 1000
                        )
                        self._log("  ✅ Challenge appears resolved.")
                        await self._random_delay(1.0, 2.5)
                        return True
                    except PlaywrightTimeout:
                        # Challenge still visible — try waiting for navigation instead
                        self._log("  ⏳ Challenge still visible, waiting for page change...")
                        try:
                            await page.wait_for_url("**", timeout=15000)
                            return True
                        except PlaywrightTimeout:
                            self._log("  ⚠ Challenge timeout — may need manual intervention.")
                            return True
            except Exception:
                continue

        return False

    # ─── Form Detection & Submission ─────────────────────────────────────────

    async def _find_and_click_submit(self, page: Page) -> bool:
        """Locate the submit button/link on the ouo.io form and click it.

        Tries multiple known selectors in priority order.

        Returns True if a submit element was found and clicked.
        """
        submit_selectors = [
            "#btn-main",
            "#btn-go",
            "#form-go button[type='submit']",
            "#form-go input[type='submit']",
            "button.btn-primary",
            "a.btn.btn-primary.btn-go",
            "a.btn.btn-go",
            "#form-go .btn",
            "form button",
            "form input[type='submit']",
        ]

        for selector in submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()

                    if is_visible and is_enabled:
                        # Scroll into view and click with human-like delay
                        try:
                            await element.scroll_into_view_if_needed(timeout=3000)
                        except Exception:
                            pass

                        await self._random_delay(0.5, 1.5)

                        # Get bounding box for natural click position
                        box = await element.bounding_box()
                        if box and box["width"] > 0 and box["height"] > 0:
                            click_x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
                            click_y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)
                            await self._human_mouse_move(page, int(click_x), int(click_y))
                            await asyncio.sleep(random.uniform(0.1, 0.3))
                            await page.mouse.click(click_x, click_y)
                        else:
                            await element.click(timeout=5000)

                        self._log(f"  🖱 Clicked submit element: {selector}")
                        return True
            except Exception as e:
                continue

        # Fallback: try to submit the form via JavaScript
        try:
            form_exists = await page.query_selector("#form-go")
            if form_exists:
                await page.evaluate("document.getElementById('form-go').submit()")
                self._log("  🖱 Submitted form via JavaScript fallback")
                return True
        except Exception:
            pass

        return False

    async def _wait_for_countdown(self, page: Page):
        """Wait for any countdown timer on the page to expire."""
        # Check for common countdown patterns
        countdown_selectors = [
            "#timer",
            ".timer",
            "#countdown",
            ".countdown",
            "#count",
            "span.seconds",
        ]

        for selector in countdown_selectors:
            try:
                timer_el = await page.query_selector(selector)
                if timer_el and await timer_el.is_visible():
                    self._log(f"  ⏱ Countdown timer detected ({selector}) — waiting...")
                    # Poll until timer reaches 0 or disappears
                    for _ in range(self.countdown_wait * 2):  # check every 0.5s
                        try:
                            text = await timer_el.text_content()
                            if text and text.strip() in ("0", "00", ""):
                                break
                            visible = await timer_el.is_visible()
                            if not visible:
                                break
                        except Exception:
                            break
                        await asyncio.sleep(0.5)
                    self._log("  ✅ Countdown complete.")
                    await self._random_delay(0.5, 1.5)
                    return
            except Exception:
                continue

        # Generic wait — some ouo pages use JS delays without visible countdown
        await self._random_delay(2.0, 4.0)

    async def _wait_for_submit_enabled(self, page: Page):
        """Wait for the submit button inside #form-go to become enabled/visible.

        ouo.io typically disables the submit button during a countdown.
        This method polls until the button is enabled or a timeout is reached.
        """
        submit_selectors = [
            "#btn-main", "#btn-go",
            "#form-go button[type='submit']",
            "#form-go input[type='submit']",
            "#form-go .btn",
        ]

        max_wait = self.countdown_wait + 5  # seconds
        self._log(f"  ⏱ Waiting for submit button to become enabled (up to {max_wait}s)...")

        for _ in range(max_wait * 2):  # check every 0.5s
            for selector in submit_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        is_visible = await el.is_visible()
                        is_enabled = await el.is_enabled()
                        if is_visible and is_enabled:
                            self._log(f"  ✅ Submit button ({selector}) is enabled and visible")
                            return
                except Exception:
                    continue
            await asyncio.sleep(0.5)

        self._log("  ⚠ Submit button still not enabled after wait — proceeding anyway")

    # ─── Popup / New Tab Handling ────────────────────────────────────────────

    async def _close_popups(self, context: BrowserContext, main_page: Page):
        """Close any popup/new tabs that are not the main page."""
        pages = context.pages
        for p in pages:
            if p != main_page:
                try:
                    await p.close()
                    self._log("  🗑 Closed popup/ad tab")
                except Exception:
                    pass

    # ─── Core Bypass Flow ────────────────────────────────────────────────────

    def _solve_turnstile_uc(self, driver) -> bool:
        """Tackle and auto-click Cloudflare Turnstile verification.

        Actively detects Turnstile challenge iframes, widgets, or 'Just a moment...' screens
        in both headed and headless modes. Searches for the verification checkbox and clicks it
        via multiple fallbacks (native click, iframe context switch, ActionChains offset, and CDP).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains

        max_wait = self.challenge_wait_timeout
        start_t = time.time()
        last_click_t = 0

        while time.time() - start_t < max_wait:
            title = (driver.title or "").lower()
            
            # Check if real content or action buttons exist
            has_action_buttons = bool(driver.find_elements(By.CSS_SELECTOR, "#btn-main, #form-captcha, #form-go, .btn-main, .btn-go"))
            is_cf_title = "just a moment" in title or "security verification" in title or "attention required" in title

            if not is_cf_title:
                # If title is normal and we have action buttons or no challenge iframe, challenge is cleared
                cf_iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
                visible_cf_iframe = any(f.is_displayed() for f in cf_iframes) if cf_iframes else False
                if has_action_buttons or not visible_cf_iframe:
                    self._log("  ✅ Cloudflare challenge cleared / page ready.")
                    return True

            self._log("  🔒 Cloudflare Turnstile verification detected — tackling and auto-clicking...")

            now = time.time()
            if now - last_click_t > 2.0:
                clicked = False

                # 1. Look for Cloudflare / Turnstile iframes
                iframes = driver.find_elements(
                    By.CSS_SELECTOR,
                    "iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='Cloudflare'], iframe[id*='cf-chl-widget']"
                )
                if not iframes:
                    for f in driver.find_elements(By.TAG_NAME, "iframe"):
                        try:
                            rect = f.rect
                            if rect["width"] > 40 and rect["height"] > 20:
                                iframes.append(f)
                        except Exception:
                            pass

                for f in iframes:
                    try:
                        rect = f.rect
                        if rect["width"] < 40 or rect["height"] < 20:
                            continue

                        # Method A: Switch into iframe and click checkbox element
                        try:
                            driver.switch_to.frame(f)
                            for sel in ["input[type='checkbox']", ".ctp-checkbox-label", "#cf-stage input", "span.mark", "body"]:
                                targets = driver.find_elements(By.CSS_SELECTOR, sel)
                                for target in targets:
                                    if target.is_displayed():
                                        target.click()
                                        self._log(f"  👉 Clicked Turnstile checkbox inside iframe ({sel})")
                                        clicked = True
                                        last_click_t = now
                                        break
                                if clicked:
                                    break
                            driver.switch_to.default_content()
                        except Exception:
                            driver.switch_to.default_content()

                        # Method B: ActionChains click offset
                        if not clicked:
                            try:
                                click_x = int(rect["width"] * 0.15) if rect["width"] > 60 else 30
                                click_y = int(rect["height"] / 2)
                                ActionChains(driver).move_to_element_with_offset(f, click_x, click_y).click().perform()
                                self._log("  👉 Clicked Turnstile iframe offset via ActionChains")
                                clicked = True
                                last_click_t = now
                            except Exception:
                                pass

                        # Method C: CDP trusted mouse click
                        if not clicked:
                            try:
                                cx = int(rect["x"] + (rect["width"] * 0.15 if rect["width"] > 60 else 30))
                                cy = int(rect["y"] + rect["height"] / 2)
                                driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                                driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                                driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                                self._log(f"  👉 Dispatched CDP mouse click at ({cx}, {cy})")
                                clicked = True
                                last_click_t = now
                            except Exception:
                                pass

                        if clicked:
                            break
                    except Exception:
                        pass

                # 2. Check for container elements in main DOM if iframe didn't respond
                if not clicked:
                    containers = driver.find_elements(
                        By.CSS_SELECTOR,
                        "div[id^='cf-chl-widget'], div.cf-turnstile, #turnstile-wrapper, #XWAst9"
                    )
                    for c in containers:
                        try:
                            rect = c.rect
                            if rect["width"] > 40 and rect["height"] > 20:
                                ActionChains(driver).move_to_element_with_offset(c, 30, int(rect["height"] / 2)).click().perform()
                                self._log("  👉 Clicked Turnstile container element")
                                last_click_t = now
                                break
                        except Exception:
                            pass

            time.sleep(1.5)

        title = (driver.title or "").lower()
        return "just a moment" not in title

    def _adapt_and_click_verify_uc(self, driver) -> bool:
        """Adaptively find and click 'Click to verify' or similar verification buttons on any page.
        
        Handles:
        - "Click to verify", "CLICK TO VERIFY"
        - "Verify you are human", "I'm a human", "Verify"
        - "Click here to continue", "Continue"
        - Form submit buttons (#btn-main, #btn-go, form#form-captcha, form#form-go)
        - Removes zero-opacity / high-z-index ad overlays blocking the button
        - Clicks via native click, ActionChains, or JS execute_script
        - Falls back to form submission if necessary
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains

        # Clean/bypass transparent overlays covering the screen
        try:
            driver.execute_script("""
                const overlays = document.querySelectorAll('div, a, span');
                for (let el of overlays) {
                    const style = window.getComputedStyle(el);
                    const z = parseInt(style.zIndex, 10);
                    if (z >= 1000 && (style.opacity === '0' || style.visibility === 'hidden')) {
                        if (style.position === 'absolute' || style.position === 'fixed') {
                            el.style.pointerEvents = 'none';
                        }
                    }
                }
            """)
        except Exception:
            pass

        # Verification button selectors in priority order
        verify_xpaths = [
            # 1. Exact or partial "Click to verify"
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click to verify')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click to verify')]",
            "//input[(@type='submit' or @type='button') and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click to verify')]",
            "//div[@role='button' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click to verify')]",
            # 2. "Verify" variants (excluding Cloudflare footer text)
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cloudflare'))]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cloudflare'))]",
            "//input[(@type='submit' or @type='button') and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify')]",
            # 3. "I'm a human" / "Human verification"
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'human')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'human')]",
            "//input[(@type='submit' or @type='button') and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'human')]",
            # 4. Standard OUO form buttons
            "//*[@id='btn-main']",
            "//*[@id='btn-go']",
            "//form[@id='form-captcha']//button",
            "//form[@id='form-captcha']//input[@type='submit']",
            "//form[@id='form-go']//button",
            "//form[@id='form-go']//input[@type='submit']",
            # 5. "Continue" / "Get Link" variants
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get link')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get link')]",
            "//a[contains(@class, 'btn-main') or contains(@class, 'btn-go')]",
            "//button[contains(@class, 'btn-main') or contains(@class, 'btn-go')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click here to continue')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click here to continue')]",
        ]

        for xpath in verify_xpaths:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                for btn in elements:
                    try:
                        if not btn.is_displayed():
                            continue

                        btn_text = (btn.text or btn.get_attribute("value") or btn.get_attribute("id") or "button").strip()
                        self._log(f"  👉 Found verification/action button: [{btn_text}]")

                        # Scroll into view
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", btn)
                        time.sleep(0.3)

                        # Remove any overlay sitting directly on top of the button
                        try:
                            driver.execute_script("""
                                const el = arguments[0];
                                const rect = el.getBoundingClientRect();
                                const topEl = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
                                if (topEl && topEl !== el && !el.contains(topEl)) {
                                    topEl.remove();
                                }
                            """, btn)
                        except Exception:
                            pass

                        # Click attempts: native -> ActionChains -> JS
                        clicked = False
                        try:
                            btn.click()
                            clicked = True
                        except Exception:
                            try:
                                ActionChains(driver).move_to_element(btn).click().perform()
                                clicked = True
                            except Exception:
                                try:
                                    driver.execute_script("arguments[0].click();", btn)
                                    clicked = True
                                except Exception:
                                    pass

                        if clicked:
                            self._log(f"  ✅ Clicked verification button: [{btn_text}]")
                            return True
                    except Exception:
                        continue
            except Exception:
                continue

        # Fallback: check if #form-captcha or #form-go exists and can be submitted
        try:
            submitted = driver.execute_script("""
                const fCaptcha = document.getElementById('form-captcha');
                if (fCaptcha) { fCaptcha.submit(); return true; }
                const fGo = document.getElementById('form-go');
                if (fGo) { fGo.submit(); return true; }
                return false;
            """)
            if submitted:
                self._log("  👉 Fallback: Submitted verification form via JavaScript")
                return True
        except Exception:
            pass

        return False

    def bypass_single_link_uc(
        self,
        ouo_url: str,
        session_id: str,
    ) -> Dict[str, Any]:
        """Navigate through ouo.io shortlink using Undetected-Chromedriver (UC).

        Adaptively clicks 'Click to verify' / 'I'm a human' on any page,
        tackles Cloudflare Turnstile in both headed and headless modes,
        intercepts and closes ad popups, waits 5s on /go/ before clicking Get Link,
        and stays at least 7 seconds on the final destination URL.
        """
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By

        self._log(f"  🔗 [Undetected-Chromedriver] Processing: {ouo_url}")
        start_time = time.time()
        result: Dict[str, Any] = {
            "ouo_url": ouo_url,
            "destination_url": None,
            "status": "pending",
            "steps": [],
            "duration": 0,
            "error": None,
            "screenshots": [],
        }

        driver = None
        try:
            self._log("  🚀 Launching undetected-chromedriver (USA locale / anti-detect)...")
            options = uc.ChromeOptions()
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--lang=en-US")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--start-maximized")

            # Headless vs Headful
            driver = uc.Chrome(options=options, headless=self.headless)
            driver.set_page_load_timeout(self.page_load_timeout)

            # Step 1: Navigate to ouo URL
            self._log(f"  📡 Navigating to: {ouo_url}...")
            driver.get(ouo_url)
            time.sleep(random.uniform(2.5, 4.0))

            # Initial Turnstile check
            self._solve_turnstile_uc(driver)

            ad_domains = [
                "about:blank", "srvqk", "pwpnotif", "adexchangerapid",
                "adsco.re", "weedsyearday", "pubadx", "popcash", "propellerads",
                "trafficjunky", "syndication", "exoclick"
            ]

            max_loop_seconds = 75
            start_loop = time.time()
            destination_found = False
            entered_go_time = None
            step_count = 1
            result["steps"].append({"step": step_count, "action": "navigate", "url": driver.current_url})

            self._log("  🔄 Starting adaptive verification and navigation loop...")

            while time.time() - start_loop < max_loop_seconds:
                time.sleep(1.2)

                # 1. Inspect window handles, close popup ad tabs, refocus on main or destination tab
                handles = list(driver.window_handles)
                ouo_handle = None
                dest_handle = None

                for h in handles:
                    try:
                        driver.switch_to.window(h)
                        cur_h_url = driver.current_url
                        if any(ad in cur_h_url for ad in ad_domains):
                            if len(driver.window_handles) > 1:
                                self._log(f"  🗑 Closed popup ad tab: {cur_h_url[:60]}")
                                driver.close()
                        elif any(domain in cur_h_url for domain in ["ouo.io", "ouo.press"]):
                            ouo_handle = h
                        elif cur_h_url.startswith("http") and "about:blank" not in cur_h_url:
                            dest_handle = h
                    except Exception:
                        pass

                # If destination handle exists and no active ouo handle
                if dest_handle and not ouo_handle:
                    driver.switch_to.window(dest_handle)
                elif ouo_handle:
                    driver.switch_to.window(ouo_handle)
                elif driver.window_handles:
                    driver.switch_to.window(driver.window_handles[0])

                cur_url = driver.current_url
                cur_title = (driver.title or "").lower()

                # 2. Check if we have reached the destination URL
                if (
                    "ouo.io" not in cur_url
                    and "ouo.press" not in cur_url
                    and "about:blank" not in cur_url
                    and not any(ad in cur_url for ad in ad_domains)
                    and cur_url.startswith("http")
                ):
                    self._log(f"  🎯 Reached destination candidate: {cur_url}")

                    # Check if destination itself has Cloudflare Turnstile or 'Click to verify'
                    if "just a moment" in cur_title or "security verification" in cur_title:
                        self._log("  🔒 Destination page has Cloudflare challenge — tackling...")
                        self._solve_turnstile_uc(driver)

                    # Adapt and click any 'Click to verify' on the destination page if present
                    self._adapt_and_click_verify_uc(driver)

                    result["destination_url"] = driver.current_url
                    result["status"] = "success"
                    destination_found = True
                    self._log(f"  🎯 FINAL DESTINATION CONFIRMED: {driver.current_url}")
                    break

                # 3. Check for Cloudflare Turnstile on current page
                if "just a moment" in cur_title or "security verification" in cur_title:
                    self._solve_turnstile_uc(driver)
                    continue

                # 4. If on /go/ page, handle countdown and 'Get Link'
                if "/go/" in cur_url:
                    if entered_go_time is None:
                        entered_go_time = time.time()
                        self._log(f"  📍 Arrived on /go/ page ({cur_url}) — waiting 5 seconds as required...")

                    elapsed_on_go = time.time() - entered_go_time
                    if elapsed_on_go < 5.0:
                        remain = 5.0 - elapsed_on_go
                        self._log(f"  ⏱ Waiting {remain:.1f}s more on /go/ page...")
                        time.sleep(remain)

                    # Now on /go/ after 5s wait: adaptively click "Get Link" or "Click to verify"
                    clicked = self._adapt_and_click_verify_uc(driver)
                    if clicked:
                        step_count += 1
                        result["steps"].append({"step": step_count, "action": "click_get_link", "url": cur_url})
                        time.sleep(2.0)
                        continue

                # 5. On initial or intermediate OUO page (not /go/ yet): adaptively click "Click to verify" / "I'm a human"
                else:
                    clicked = self._adapt_and_click_verify_uc(driver)
                    if clicked:
                        step_count += 1
                        result["steps"].append({"step": step_count, "action": "click_verify", "url": cur_url})
                        time.sleep(2.0)
                        continue

            if destination_found:
                dwell = max(7.0, random.uniform(self.destination_dwell_min, self.destination_dwell_max))
                self._log(f"  ⏳ Dwelling on destination for at least {dwell:.1f}s...")
                time.sleep(dwell)

                if self.take_screenshots:
                    ss_path = os.path.join(self.screenshot_dir, f"{session_id}_destination.png")
                    try:
                        driver.save_screenshot(ss_path)
                        result["screenshots"].append(ss_path)
                        self._log(f"  📸 Screenshot saved: {ss_path}")
                    except Exception as ss_err:
                        self._log(f"  ⚠ Screenshot notice: {ss_err}")
            else:
                result["status"] = "failed"
                handles_urls = []
                for h in driver.window_handles:
                    try:
                        driver.switch_to.window(h)
                        handles_urls.append(driver.current_url)
                    except Exception:
                        pass
                result["error"] = f"Did not reach destination within timeout. Active tabs: {handles_urls}"
                self._log(f"  ❌ {result['error']}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._log(f"  ❌ Undetected-Chromedriver Exception: {e}")
        finally:
            result["duration"] = round(time.time() - start_time, 2)
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return result

    async def bypass_single_link_nodriver(
        self,
        ouo_url: str,
        session_id: str,
    ) -> Dict[str, Any]:
        """Navigate through ouo.io shortlink using Nodriver (CDP-free anti-detection browser).

        Clicks step-by-step:
        1. Navigates to link
        2. Clicks 'I'm a human' button (#btn-main)
        3. Waits 5 seconds
        4. Clicks 'Get Link' button (#btn-main / #btn-go / a.btn-go)
        5. Handles popups and monitors until final destination is reached
        """
        import nodriver as uc

        self._log(f"  🔗 [Nodriver] Processing: {ouo_url}")
        start_time = time.time()
        result: Dict[str, Any] = {
            "ouo_url": ouo_url,
            "destination_url": None,
            "status": "pending",
            "steps": [],
            "duration": 0,
            "error": None,
            "screenshots": [],
        }

        browser = None
        try:
            self._log("  🚀 Launching nodriver browser (USA locale / anti-detect)...")
            browser_args = [
                "--disable-popup-blocking",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            browser = await uc.start(
                headless=self.headless,
                lang="en-US",
                browser_args=browser_args,
            )

            # Step 1: Navigate to ouo.io URL
            self._log(f"  📡 Navigating to: {ouo_url}...")
            page = await browser.get(ouo_url)
            await page.sleep(random.uniform(2.5, 3.5))

            result["steps"].append({"step": 1, "action": "navigate", "url": page.url})
            self._log(f"  📍 Step 1: Landed on {page.url}")

            ad_domains = [
                "about:blank", "srvqk", "pwpnotif", "adexchangerapid",
                "adsco.re", "weedsyearday", "pubadx", "popcash", "propellerads",
                "trafficjunky", "syndication", "exoclick"
            ]

            async def _adapt_click_nodriver(target_page) -> bool:
                try:
                    js_code = """
                    (() => {
                        const overlays = document.querySelectorAll('div, a, span');
                        for (let el of overlays) {
                            const style = window.getComputedStyle(el);
                            const z = parseInt(style.zIndex, 10);
                            if (z >= 1000 && (style.opacity === '0' || style.visibility === 'hidden')) {
                                if (style.position === 'absolute' || style.position === 'fixed') {
                                    el.style.pointerEvents = 'none';
                                }
                            }
                        }

                        const candidates = Array.from(document.querySelectorAll('button, a, input[type="submit"], input[type="button"], div[role="button"]'));
                        const keywords = ['click to verify', 'verify', 'human', 'get link', 'continue'];

                        for (const kw of keywords) {
                            for (const el of candidates) {
                                const txt = (el.innerText || el.textContent || el.value || el.id || '').toLowerCase();
                                if (txt.includes(kw) && !txt.includes('cloudflare')) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width > 0 && rect.height > 0) {
                                        el.scrollIntoView({block: 'center', inline: 'center'});
                                        el.click();
                                        return true;
                                    }
                                }
                            }
                        }

                        const mainBtn = document.querySelector('#btn-main, #btn-go, a.btn-go, button.btn-main');
                        if (mainBtn) {
                            mainBtn.click();
                            return true;
                        }

                        const fCaptcha = document.getElementById('form-captcha');
                        if (fCaptcha) { fCaptcha.submit(); return true; }
                        const fGo = document.getElementById('form-go');
                        if (fGo) { fGo.submit(); return true; }

                        return false;
                    })()
                    """
                    res = await target_page.evaluate(js_code)
                    return bool(res)
                except Exception:
                    return False

            max_loop_seconds = 75
            start_loop = time.time()
            destination_tab = None
            entered_go_time = None
            step_count = 1

            self._log("  🔄 Starting adaptive verification and navigation loop (Nodriver)...")

            while time.time() - start_loop < max_loop_seconds:
                await page.sleep(1.2)

                # 1. Close popup ads and track main ouo or destination tab
                tabs = list(browser.tabs)
                ouo_tab = None
                dest_tab = None

                for t in tabs:
                    t_url = t.url
                    if any(ad in t_url for ad in ad_domains):
                        if len(browser.tabs) > 1:
                            try:
                                await t.close()
                                self._log(f"  🗑 Closed popup ad tab: {t_url[:60]}")
                            except Exception:
                                pass
                    elif any(domain in t_url for domain in ["ouo.io", "ouo.press"]):
                        ouo_tab = t
                    elif t_url.startswith("http") and "about:blank" not in t_url:
                        dest_tab = t

                if dest_tab and not ouo_tab:
                    page = dest_tab
                elif ouo_tab:
                    page = ouo_tab
                elif browser.tabs:
                    page = browser.tabs[0]

                cur_url = page.url
                cur_title = ""
                try:
                    cur_title = (await page.evaluate("document.title") or "").lower()
                except Exception:
                    pass

                # 2. Check if destination reached
                if (
                    "ouo.io" not in cur_url
                    and "ouo.press" not in cur_url
                    and "about:blank" not in cur_url
                    and not any(ad in cur_url for ad in ad_domains)
                    and cur_url.startswith("http")
                ):
                    self._log(f"  🎯 Reached destination candidate: {cur_url}")

                    # Check for Cloudflare Turnstile on destination
                    if "just a moment" in cur_title or "security verification" in cur_title:
                        try:
                            w = await page.select("iframe[src*='challenges.cloudflare.com'], div[id^='cf-chl-widget'], #XWAst9", timeout=3)
                            if w:
                                await w.click()
                        except Exception:
                            pass

                    # Adaptively click any verify button on destination
                    await _adapt_click_nodriver(page)

                    destination_tab = page
                    result["destination_url"] = cur_url
                    result["status"] = "success"
                    self._log(f"  🎯 FINAL DESTINATION CONFIRMED: {cur_url}")
                    break

                # 3. Check for Cloudflare Turnstile on current page
                if "just a moment" in cur_title or "security verification" in cur_title:
                    self._log("  🔒 Cloudflare Turnstile active — tackling in Nodriver...")
                    try:
                        w = await page.select("iframe[src*='challenges.cloudflare.com'], div[id^='cf-chl-widget'], #XWAst9", timeout=3)
                        if w:
                            await w.click()
                            self._log("  👉 Clicked Turnstile widget in Nodriver")
                    except Exception:
                        pass
                    continue

                # 4. If on /go/ page, wait 5 seconds and click Get Link
                if "/go/" in cur_url:
                    if entered_go_time is None:
                        entered_go_time = time.time()
                        self._log(f"  📍 Arrived on /go/ page ({cur_url}) — waiting 5 seconds as required...")

                    elapsed_on_go = time.time() - entered_go_time
                    if elapsed_on_go < 5.0:
                        remain = 5.0 - elapsed_on_go
                        self._log(f"  ⏱ Waiting {remain:.1f}s more on /go/ page...")
                        await page.sleep(remain)

                    clicked = await _adapt_click_nodriver(page)
                    if clicked:
                        step_count += 1
                        result["steps"].append({"step": step_count, "action": "click_get_link", "url": cur_url})
                        self._log("  👉 Clicked 'Get Link' / action button on /go/ page")
                        await page.sleep(2.0)
                        continue

                # 5. On initial or intermediate page: adaptively click "Click to verify" / "I'm a human"
                else:
                    clicked = await _adapt_click_nodriver(page)
                    if clicked:
                        step_count += 1
                        result["steps"].append({"step": step_count, "action": "click_verify", "url": cur_url})
                        self._log("  👉 Clicked 'Click to verify' / action button")
                        await page.sleep(2.0)
                        continue

            if result["status"] == "success" and destination_tab:
                # Dwell on destination (minimum 7 seconds as requested)
                dwell = max(7.0, random.uniform(self.destination_dwell_min, self.destination_dwell_max))
                self._log(f"  ⏳ Dwelling on destination for at least {dwell:.1f}s...")
                await page.sleep(dwell)

                # Save screenshot if enabled
                if self.take_screenshots:
                    ss_path = os.path.join(self.screenshot_dir, f"{session_id}_destination.png")
                    try:
                        await destination_tab.save_screenshot(ss_path)
                        result["screenshots"].append(ss_path)
                        self._log(f"  📸 Screenshot saved: {ss_path}")
                    except Exception as ss_err:
                        self._log(f"  ⚠ Screenshot notice: {ss_err}")
            elif result["status"] != "success":
                result["status"] = "failed"
                result["error"] = f"Did not reach destination within timeout. Tabs: {[t.url for t in browser.tabs]}"
                self._log(f"  ❌ {result['error']}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._log(f"  ❌ Nodriver Exception: {e}")
        finally:
            result["duration"] = round(time.time() - start_time, 2)
            if browser:
                try:
                    browser.stop()
                except Exception:
                    pass

        return result

    async def bypass_single_link(
        self,
        ouo_url: str,
        context: BrowserContext,
        session_id: str,
    ) -> Dict[str, Any]:
        """Navigate through a single ouo.io link to reach its final destination.

        Args:
            ouo_url: The ouo.io short link to bypass.
            context: Playwright BrowserContext to use.
            session_id: Session identifier for logging/screenshots.

        Returns:
            Dict with keys: ouo_url, destination_url, status, steps, duration, error
        """
        self._log(f"  🔗 Processing: {ouo_url}")
        page = await context.new_page()

        result: Dict[str, Any] = {
            "ouo_url": ouo_url,
            "destination_url": None,
            "status": "pending",
            "steps": [],
            "duration": 0,
            "error": None,
            "screenshots": [],
        }

        start_time = time.time()
        step_count = 0
        max_steps = 10  # Safety limit to prevent infinite loops

        try:
            # Step 1: Navigate to the ouo.io URL
            self._log(f"  📡 Loading page...")
            await page.goto(ouo_url, wait_until="domcontentloaded", timeout=self.page_load_timeout * 1000)
            await self._random_delay(2.0, 4.0)

            step_count += 1
            result["steps"].append({"step": step_count, "action": "initial_load", "url": page.url})
            self._log(f"  📍 Step {step_count}: Landed on {page.url}")

            # Screenshot after initial load
            ss = await self._take_screenshot(page, f"step{step_count}_load", session_id)
            if ss:
                result["screenshots"].append(ss)

            while step_count < max_steps:
                # Check if we've reached the destination
                if await self._is_destination_reached(page, ouo_url):
                    result["destination_url"] = page.url
                    result["status"] = "success"
                    self._log(f"  🎯 DESTINATION REACHED: {page.url}")
                    break

                # Close any popup tabs that opened
                await self._close_popups(context, page)

                # Handle Cloudflare challenge if present
                challenge_found = await self._wait_for_challenge(page)
                if challenge_found:
                    step_count += 1
                    result["steps"].append({"step": step_count, "action": "challenge_wait", "url": page.url})
                    self._log(f"  📍 Step {step_count}: Challenge handled at {page.url}")
                    await self._random_delay(1.5, 3.0)

                    # Re-check if we navigated away during challenge
                    if await self._is_destination_reached(page, ouo_url):
                        result["destination_url"] = page.url
                        result["status"] = "success"
                        self._log(f"  🎯 DESTINATION REACHED: {page.url}")
                        break

                # Simulate human behavior — scroll and read
                await self._simulate_reading(page)

                # Wait for any countdown timer
                await self._wait_for_countdown(page)

                # Actively wait for form#form-go to appear (ouo.io /go/ pages load it
                # after Cloudflare resolves and JS executes, which can take several seconds)
                form_found = await page.query_selector("#form-go")
                if not form_found:
                    self._log(f"  ⏳ Waiting for form#form-go to appear (up to {self.form_wait_timeout}s)...")
                    try:
                        await page.wait_for_selector(
                            "#form-go", state="attached", timeout=self.form_wait_timeout * 1000
                        )
                        form_found = await page.query_selector("#form-go")
                        if form_found:
                            self._log("  ✅ Form#form-go appeared!")
                            # Give the form a moment to fully render
                            await self._random_delay(1.0, 2.0)
                    except PlaywrightTimeout:
                        self._log("  ⚠ Form#form-go did not appear within timeout.")

                # Look for the form and submit button
                if form_found:
                    self._log(f"  📋 Found form#form-go — preparing to submit...")

                    # Wait for the submit button to become enabled
                    # (ouo.io often disables the button during a countdown)
                    await self._wait_for_submit_enabled(page)

                    # Wait for navigation after click
                    try:
                        async with page.expect_navigation(
                            timeout=self.page_load_timeout * 1000,
                            wait_until="domcontentloaded",
                        ):
                            clicked = await self._find_and_click_submit(page)
                            if not clicked:
                                self._log("  ⚠ Could not find submit button — trying JS submit")
                                await page.evaluate("document.getElementById('form-go').submit()")
                    except PlaywrightTimeout:
                        self._log("  ⚠ Navigation timeout after form submit — checking page state...")
                    except Exception as nav_err:
                        self._log(f"  ⚠ Navigation error: {nav_err}")

                    step_count += 1
                    result["steps"].append({"step": step_count, "action": "form_submit", "url": page.url})
                    self._log(f"  📍 Step {step_count}: After form submit → {page.url}")

                    ss = await self._take_screenshot(page, f"step{step_count}_submit", session_id)
                    if ss:
                        result["screenshots"].append(ss)

                    await self._random_delay(2.0, 4.0)
                else:
                    # No form found — look for any clickable "continue" type link/button
                    continue_selectors = [
                        "a:has-text('Continue')",
                        "a:has-text('Get Link')",
                        "a:has-text('Go to Link')",
                        "a:has-text('Click here')",
                        "button:has-text('Continue')",
                        "button:has-text('Get Link')",
                        "#btn-main",
                        "#btn-go",
                        ".btn-go",
                    ]

                    clicked_continue = False
                    for sel in continue_selectors:
                        try:
                            el = await page.query_selector(sel)
                            if el and await el.is_visible():
                                try:
                                    async with page.expect_navigation(
                                        timeout=self.page_load_timeout * 1000,
                                        wait_until="domcontentloaded",
                                    ):
                                        await el.click(timeout=5000)
                                except (PlaywrightTimeout, Exception):
                                    pass
                                clicked_continue = True
                                step_count += 1
                                result["steps"].append({
                                    "step": step_count,
                                    "action": f"click_{sel}",
                                    "url": page.url,
                                })
                                self._log(f"  📍 Step {step_count}: Clicked '{sel}' → {page.url}")
                                await self._random_delay(2.0, 4.0)
                                break
                        except Exception:
                            continue

                    if not clicked_continue:
                        # Maybe we're already at destination or page is stuck
                        self._log(f"  ⚠ No form or continue button found on {page.url}")

                        # Wait longer for any late-loading elements or redirects
                        self._log("  ⏳ Waiting for page changes (up to 15s)...")
                        try:
                            # Wait for ANY navigation or URL change
                            await page.wait_for_url(
                                lambda url: not any(d in url for d in ["ouo.io", "ouo.press"]),
                                timeout=15000,
                            )
                            if await self._is_destination_reached(page, ouo_url):
                                result["destination_url"] = page.url
                                result["status"] = "success"
                                self._log(f"  🎯 DESTINATION REACHED (via redirect): {page.url}")
                                break
                        except PlaywrightTimeout:
                            pass

                        # Last resort: try waiting for form one more time (Cloudflare may
                        # have reloaded the page, and the form takes time to render)
                        self._log("  ⏳ Last attempt: waiting for form#form-go or any button...")
                        try:
                            await page.wait_for_selector(
                                "#form-go, #btn-main, #btn-go, .btn-go, a.btn",
                                state="visible",
                                timeout=15000,
                            )
                            # Found something — loop back to try again
                            self._log("  ✅ Found interactive element — retrying flow...")
                            continue
                        except PlaywrightTimeout:
                            pass

                        # Final fallback — if URL hasn't changed, break to avoid infinite loop
                        self._log("  ❌ Stuck — unable to proceed further.")
                        result["status"] = "stuck"
                        result["error"] = f"Unable to find next action on {page.url}"
                        break

                # Close any new popups after each step
                await self._close_popups(context, page)

            # If we exhausted steps without reaching destination
            if result["status"] == "pending":
                result["status"] = "max_steps_reached"
                result["error"] = f"Reached max {max_steps} steps without finding destination"
                self._log(f"  ⚠ Max steps ({max_steps}) reached. Last URL: {page.url}")

            # If destination was reached, dwell on the final page
            if result["status"] == "success":
                dwell = max(7.0, random.uniform(self.destination_dwell_min, self.destination_dwell_max))
                self._log(f"  ⏳ Dwelling on destination for at least {dwell:.1f}s...")
                await self._simulate_reading(page)
                await asyncio.sleep(dwell)

                ss = await self._take_screenshot(page, "destination", session_id)
                if ss:
                    result["screenshots"].append(ss)

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._log(f"  ❌ Error processing {ouo_url}: {e}")
        finally:
            result["duration"] = round(time.time() - start_time, 2)
            try:
                await page.close()
            except Exception:
                pass

        return result

    # ─── Session Runners ─────────────────────────────────────────────────────

    async def run_continuous(
        self,
        links: List[str],
        link_delay_min: float = 15.0,
        link_delay_max: float = 45.0,
    ):
        """Run the bypass in an unlimited continuous loop, picking random links.

        Args:
            links: Pool of ouo.io URLs to pick from.
            link_delay_min: Minimum seconds between link processing.
            link_delay_max: Maximum seconds between link processing.
        """
        cycle = 0
        successes = 0
        failures = 0
        last_url = None
        start_time = time.time()

        self._log("=" * 65)
        self._log("  🔄 OUO.io BYPASS — UNLIMITED CONTINUOUS LOOP")
        self._log("=" * 65)
        self._log(f"  Links pool:     {len(links)} URLs loaded")
        self._log(f"  Engine:         {self.engine_type.upper()}")
        self._log(f"  Headless:       {self.headless}")
        self._log(f"  Link delay:     {link_delay_min}s – {link_delay_max}s between links")
        self._log(f"  Destination dwell: {self.destination_dwell_min}s – {self.destination_dwell_max}s")
        self._log("=" * 65)
        self._log("  Press Ctrl+C to stop at any time.\n")

        if self.engine_type in ("uc", "undetected", "undetected-chromedriver"):
            await self._run_continuous_uc(links, link_delay_min, link_delay_max, start_time)
            return

        if self.engine_type == "nodriver":
            await self._run_continuous_nodriver(links, link_delay_min, link_delay_max, start_time)
            return

        async with async_playwright() as p:

            try:
                while True:
                    cycle += 1
                    elapsed = time.time() - start_time
                    elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

                    # Pick a random link (avoid repeating the same one twice)
                    from .link_loader import pick_random_link
                    url = pick_random_link(links, exclude=last_url)
                    last_url = url

                    self._log(f"\n{'─' * 65}")
                    self._log(
                        f"  📋 Cycle #{cycle} | ✅ {successes} ok | ❌ {failures} fail | "
                        f"⏱ {elapsed_m}m{elapsed_s}s elapsed"
                    )
                    self._log(f"{'─' * 65}")

                    # Fresh fingerprint each cycle for anti-detection
                    fingerprint = generate_fingerprint()
                    context_opts = get_context_options(fingerprint)
                    launch_args = get_launch_args()
                    stealth_script = get_stealth_script(fingerprint)

                    self._log(f"  🎭 Fingerprint: {fingerprint.platform} | "
                              f"{fingerprint.viewport_width}x{fingerprint.viewport_height} | "
                              f"{fingerprint.timezone}")

                    browser = await p.chromium.launch(
                        headless=self.headless,
                        args=launch_args,
                    )
                    context = await browser.new_context(**context_opts)
                    await context.add_init_script(stealth_script)

                    session_id = f"ouo_c{cycle}_{int(time.time())}"

                    try:
                        result = await self.bypass_single_link(url, context, session_id)

                        if result["status"] == "success":
                            successes += 1
                            self._log(f"  ✅ SUCCESS — Destination: {result['destination_url']}")
                        else:
                            failures += 1
                            self._log(f"  ❌ FAILED — Status: {result['status']} | Error: {result.get('error', 'N/A')}")

                        self._log(f"  ⏱ Duration: {result['duration']}s | Steps: {len(result['steps'])}")

                    except Exception as e:
                        failures += 1
                        self._log(f"  ❌ Cycle #{cycle} EXCEPTION: {e}")
                    finally:
                        await context.close()
                        await browser.close()

                    # Random delay between links
                    delay = random.uniform(link_delay_min, link_delay_max)
                    mins = int(delay // 60)
                    secs = int(delay % 60)
                    time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    self._log(f"\n  ⏳ Waiting {delay:.1f}s (~{time_str}) before next link...")

                    try:
                        # Use small increments for responsive Ctrl+C
                        for _ in range(int(delay * 10)):
                            await asyncio.sleep(0.1)
                    except (asyncio.CancelledError, KeyboardInterrupt):
                        self._log("  Interrupted during wait.")
                        break

            except (KeyboardInterrupt, asyncio.CancelledError):
                self._log(f"\n{'=' * 65}")
                self._log(f"  🛑 LOOP STOPPED BY USER (Ctrl+C)")
                self._log(f"{'=' * 65}")
            finally:
                elapsed = time.time() - start_time
                elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

                self._log(f"\n{'=' * 65}")
                self._log(f"  📊 FINAL SUMMARY")
                self._log(f"{'=' * 65}")
                self._log(f"  Total cycles:   {cycle}")
                self._log(f"  Successful:     {successes}")
                self._log(f"  Failed:         {failures}")
                rate = (successes / max(cycle, 1)) * 100
                self._log(f"  Success rate:   {rate:.1f}%")
                self._log(f"  Total time:     {elapsed_m}m {elapsed_s}s")
                self._log(f"{'=' * 65}")

    async def _run_continuous_nodriver(
        self,
        links: List[str],
        link_delay_min: float,
        link_delay_max: float,
        start_time: float,
    ):
        """Continuous bypass loop powered by Nodriver."""
        from .link_loader import pick_random_link

        cycle = 0
        successes = 0
        failures = 0
        last_url = None

        try:
            while True:
                cycle += 1
                elapsed = time.time() - start_time
                elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

                url = pick_random_link(links, exclude=last_url)
                last_url = url

                self._log(f"\n{'─' * 65}")
                self._log(
                    f"  📋 Cycle #{cycle} (Nodriver) | ✅ {successes} ok | ❌ {failures} fail | "
                    f"⏱ {elapsed_m}m{elapsed_s}s elapsed"
                )
                self._log(f"{'─' * 65}")

                session_id = f"ouo_nd_c{cycle}_{int(time.time())}"

                try:
                    result = await self.bypass_single_link_nodriver(url, session_id)

                    if result["status"] == "success":
                        successes += 1
                        self._log(f"  ✅ SUCCESS — Destination: {result['destination_url']}")
                    else:
                        failures += 1
                        self._log(f"  ❌ FAILED — Status: {result['status']} | Error: {result.get('error', 'N/A')}")

                    self._log(f"  ⏱ Duration: {result['duration']}s | Steps: {len(result['steps'])}")

                except Exception as e:
                    failures += 1
                    self._log(f"  ❌ Cycle #{cycle} EXCEPTION: {e}")

                # Delay between links
                delay = random.uniform(link_delay_min, link_delay_max)
                mins = int(delay // 60)
                secs = int(delay % 60)
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                self._log(f"\n  ⏳ Waiting {delay:.1f}s (~{time_str}) before next link...")

                try:
                    for _ in range(int(delay * 10)):
                        await asyncio.sleep(0.1)
                except (asyncio.CancelledError, KeyboardInterrupt):
                    self._log("  Interrupted during wait.")
                    break

        except (KeyboardInterrupt, asyncio.CancelledError):
            self._log(f"\n{'=' * 65}")
            self._log(f"  🛑 LOOP STOPPED BY USER (Ctrl+C)")
            self._log(f"{'=' * 65}")
        finally:
            elapsed = time.time() - start_time
            elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

            self._log(f"\n{'=' * 65}")
            self._log(f"  📊 FINAL SUMMARY (Nodriver)")
            self._log(f"{'=' * 65}")
            self._log(f"  Total cycles:   {cycle}")
            self._log(f"  Successful:     {successes}")
            self._log(f"  Failed:         {failures}")
            rate = (successes / max(cycle, 1)) * 100
            self._log(f"  Success rate:   {rate:.1f}%")
            self._log(f"  Total time:     {elapsed_m}m {elapsed_s}s")
            self._log(f"{'=' * 65}")

    async def _run_continuous_uc(
        self,
        links: List[str],
        link_delay_min: float,
        link_delay_max: float,
        start_time: float,
    ):
        """Continuous bypass loop powered by Undetected-Chromedriver."""
        from .link_loader import pick_random_link

        cycle = 0
        successes = 0
        failures = 0
        last_url = None

        try:
            while True:
                cycle += 1
                elapsed = time.time() - start_time
                elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

                url = pick_random_link(links, exclude=last_url)
                last_url = url

                self._log(f"\n{'─' * 65}")
                self._log(
                    f"  📋 Cycle #{cycle} (Undetected-Chromedriver) | ✅ {successes} ok | ❌ {failures} fail | "
                    f"⏱ {elapsed_m}m{elapsed_s}s elapsed"
                )
                self._log(f"{'─' * 65}")

                session_id = f"ouo_uc_c{cycle}_{int(time.time())}"

                try:
                    # Run in thread executor to keep async loop responsive
                    result = await asyncio.to_thread(self.bypass_single_link_uc, url, session_id)

                    if result["status"] == "success":
                        successes += 1
                        self._log(f"  ✅ SUCCESS — Destination: {result['destination_url']}")
                    else:
                        failures += 1
                        self._log(f"  ❌ FAILED — Status: {result['status']} | Error: {result.get('error', 'N/A')}")

                    self._log(f"  ⏱ Duration: {result['duration']}s | Steps: {len(result['steps'])}")

                except Exception as e:
                    failures += 1
                    self._log(f"  ❌ Cycle #{cycle} EXCEPTION: {e}")

                # Delay between links
                delay = random.uniform(link_delay_min, link_delay_max)
                mins = int(delay // 60)
                secs = int(delay % 60)
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                self._log(f"\n  ⏳ Waiting {delay:.1f}s (~{time_str}) before next link...")

                try:
                    for _ in range(int(delay * 10)):
                        await asyncio.sleep(0.1)
                except (asyncio.CancelledError, KeyboardInterrupt):
                    self._log("  Interrupted during wait.")
                    break

        except (KeyboardInterrupt, asyncio.CancelledError):
            self._log(f"\n{'=' * 65}")
            self._log(f"  🛑 LOOP STOPPED BY USER (Ctrl+C)")
            self._log(f"{'=' * 65}")
        finally:
            elapsed = time.time() - start_time
            elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

            self._log(f"\n{'=' * 65}")
            self._log(f"  📊 FINAL SUMMARY (Undetected-Chromedriver)")
            self._log(f"{'=' * 65}")
            self._log(f"  Total cycles:   {cycle}")
            self._log(f"  Successful:     {successes}")
            self._log(f"  Failed:         {failures}")
            rate = (successes / max(cycle, 1)) * 100
            self._log(f"  Success rate:   {rate:.1f}%")
            self._log(f"  Total time:     {elapsed_m}m {elapsed_s}s")
            self._log(f"{'=' * 65}")


