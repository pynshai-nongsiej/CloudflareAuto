import os
import sys
from typing import Any, Optional
from browser_use import (
    Agent,
    BrowserSession,
    ChatAnthropic,
    ChatGoogle,
    ChatOllama,
    ChatOpenAI,
    Controller,
)
from .tempmail_client import TempMailClient
from .fingerprint import (
    generate_fingerprint,
    get_injection_script,
    get_playwright_context_options,
    get_launch_args,
)


def get_default_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Any:
    """Instantiate an LLM for browser-use based on available environment variables or options."""
    # 1. Explicit provider
    prov = (provider or "").lower().strip()

    if prov == "openai" or (not prov and os.getenv("OPENAI_API_KEY")):
        return ChatOpenAI(
            model=model_name or os.getenv("OPENAI_MODEL", "gpt-4o"),
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
        )

    if prov in ("google", "gemini") or (
        not prov and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    ):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return ChatGoogle(
            model=model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            api_key=key,
        )

    if prov == "anthropic" or (not prov and os.getenv("ANTHROPIC_API_KEY")):
        return ChatAnthropic(
            model=model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
        )

    if prov == "ollama" or (not prov and os.getenv("OLLAMA_MODEL")):
        return ChatOllama(
            model=model_name or os.getenv("OLLAMA_MODEL", "llama3.1"),
        )

    # If BROWSER_USE_API_KEY is available, browser-use will handle it natively
    if os.getenv("BROWSER_USE_API_KEY"):
        return None

    raise ValueError(
        "No LLM API key detected for browser-use.\n"
        "Please set one of the following environment variables:\n"
        "  - OPENAI_API_KEY\n"
        "  - GEMINI_API_KEY (or GOOGLE_API_KEY)\n"
        "  - ANTHROPIC_API_KEY\n"
        "  - BROWSER_USE_API_KEY\n"
        "Or use `--mode direct` to run without requiring any LLM."
    )


def create_browser_use_agent(
    mail_client: Optional[TempMailClient] = None,
    llm: Optional[Any] = None,
    headed: bool = False,
    task_instructions: Optional[str] = None,
) -> Agent:
    """Create and configure a browser-use Agent equipped with TempMail verification tools.
    
    Each invocation generates a unique randomized browser fingerprint for 
    anti-detection (user-agent, viewport, WebGL, canvas, timezone, etc.).
    """
    client = mail_client or TempMailClient()
    controller = Controller()

    # Generate a fully randomized browser fingerprint
    host_platform = {"darwin": "darwin", "win32": "win32", "linux": "linux"}.get(sys.platform, None)
    fp = generate_fingerprint(prefer_platform=host_platform)
    print(f"[Fingerprint] UA={fp.user_agent[:60]}... | Platform={fp.platform} | "
          f"GPU={fp.webgl_renderer[:30]}... | TZ={fp.timezone}")

    # Track generated inbox across actions
    state = {"current_email": None}

    @controller.action("Create a brand new temporary email address on TempMail.Plus")
    def create_temporary_email() -> str:
        """Generates a fresh temporary email address on TempMail.Plus with random name and domain ending.

        Returns:
            The newly created email address.
        """
        inbox = client.create_inbox()
        addr = inbox["address"]
        state["current_email"] = addr
        return addr

    @controller.action("Fetch the OTP verification code from the temporary email inbox")
    def fetch_verification_otp(email_address: Optional[str] = None, timeout_seconds: int = 60) -> str:
        """Polls the inbox until the 6-digit OTP verification code arrives.

        Args:
            email_address: The temporary email address (optional, defaults to last generated).
            timeout_seconds: Max seconds to wait for code arrival.
        Returns:
            The plain 6-digit OTP code string.
        """
        target = email_address or state["current_email"]
        if not target:
            return "ERROR: No email address provided and no temporary email was created yet."

        code = client.wait_for_otp(target, timeout=timeout_seconds, poll_interval=2.0)
        if not code:
            return f"ERROR: Timed out after {timeout_seconds}s waiting for OTP on {target}."
        return code

    default_task = (
        "Perform account registration and OTP verification on TenBox Websurfer:\n"
        "1. First, call `create_temporary_email` to generate a new disposable email address.\n"
        "2. Navigate to https://websurfer.1024tenbox.com/referral/J7V5V668 (this is a referral landing page).\n"
        "3. On the referral page, click the 'Get started free' button to go to the login/signup form.\n"
        "4. Wait for the login form to appear, then type the generated email address into the email input field.\n"
        "5. Click the 'Send OTP' button.\n"
        "6. Once on the OTP verification screen (/otp), call `fetch_verification_otp` to obtain the 6-digit verification code.\n"
        "7. Enter the 6 digits into the OTP boxes on the screen.\n"
        "8. Verify that registration completes and the browser redirects to the dashboard (https://websurfer.1024tenbox.com/).\n"
        "9. Finish and report the final verified email address and account status."
    )

    # Configure BrowserSession with randomized fingerprint
    ctx_options = get_playwright_context_options(fp)
    browser_session = BrowserSession(
        headless=not headed,
        browser_args=get_launch_args(),
        # Pass fingerprint-derived context options
        user_agent=fp.user_agent,
        viewport=ctx_options.get("viewport"),
        # Inject the comprehensive fingerprint spoof script
        init_script=get_injection_script(fp),
    )

    agent = Agent(
        task=task_instructions or default_task,
        llm=llm,
        controller=controller,
        browser_session=browser_session,
        use_vision=True,
    )

    return agent

