import json
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# Official dropdown domains on https://tempmail.plus/en/#!
FALLBACK_DOMAINS = [
    "mailto.plus",
    "fexpost.com",
    "fexbox.org",
    "mailbox.in.ua",
    "rover.info",
    "chitthi.in",
    "fextemp.com",
    "any.pink",
    "merepost.com",
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
API_BASE = "https://tempmail.plus"


def get_random_pre() -> str:
    """Generate a pronounceable random mailbox name using the exact TempMail.Plus algorithm.
    
    Ported directly from https://tempmail.plus index.js:
      var l = 5 + Math.floor(Math.random() * 3);
      var w = '';
      var s = ['aeouy', 'bcdfghkmnpqstvwxz'];
      var t = Math.floor(Math.random() * 2);
      var x = t ? 5 : 7;
      for (var i = 0; i < l; i++) {
          w += s[t].charAt(Math.floor(Math.random() * s[t].length));
          if (Math.floor(Math.random() * x) > 1) {
              t = 1 - t;
              x = t ? 5 : 10;
          } else {
              x += 4;
          }
      }
    """
    length = 5 + random.randint(0, 2)  # length 5 to 7
    word = ""
    sets = ["aeouy", "bcdfghkmnpqstvwxz"]
    t = random.randint(0, 1)
    x = 5 if t else 7

    for _ in range(length):
        word += random.choice(sets[t])
        if random.randint(0, x - 1) > 1:
            t = 1 - t
            x = 5 if t else 10
        else:
            x += 4

    return word


def fetch_live_domains() -> List[str]:
    """Fetch current dropdown domains directly from https://tempmail.plus/en/#!.
    
    Falls back to FALLBACK_DOMAINS if fetch fails or yields empty.
    """
    try:
        req = urllib.request.Request(
            f"{API_BASE}/en/#!",
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract dropdown items
            found = re.findall(
                r'<button[^>]*class="[^"]*dropdown-item[^"]*"[^>]*>([a-z0-9.-]+\.[a-z]{2,})</button>',
                html,
                re.IGNORECASE,
            )
            if found:
                unique_domains = list(dict.fromkeys(d.lower() for d in found))
                return unique_domains
    except Exception:
        pass
    return FALLBACK_DOMAINS


def extract_otp_code(text: str) -> Optional[str]:
    """Extract 4 to 8 digit OTP verification code from text or html."""
    if not text:
        return None
    patterns = [
        r"(?:OTP|verification code|security code|one[- ]time (?:password|code)|sign[- ]in code)\b[^\d\n]{0,70}\s*\b(\d{4,8})\b",
        r"\b(\d{4,8})\b\s*(?:is your|is the)\s*(?:OTP|verification code|security code|code)",
        r"\b(\d{6})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


class TempMailClient:
    """Client for TempMail.Plus (https://tempmail.plus/en/#!).
    
    Generates random mailbox names and random domain endings from the dropdown per signup.
    Polls the TempMail.Plus API to receive incoming verification OTP codes.
    """

    def __init__(self, api_base: Optional[str] = None, token: Optional[str] = None):
        self.api_base = (api_base or API_BASE).rstrip("/")
        self.domains: List[str] = fetch_live_domains()
        self.current_email: Optional[str] = None
        self.current_name: Optional[str] = None
        self.current_domain: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": f"{self.api_base}/en/#!",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _normalize_email(self, email_or_local: str) -> str:
        """Resolve full email address if only local part is provided."""
        if "@" in email_or_local:
            return email_or_local.strip()
        if self.current_domain:
            return f"{email_or_local.strip()}@{self.current_domain}"
        if self.current_email:
            return self.current_email
        default_domain = self.domains[0] if self.domains else FALLBACK_DOMAINS[0]
        return f"{email_or_local.strip()}@{default_domain}"

    def create_inbox(self, clean: bool = True, domain: Optional[str] = None) -> Dict[str, Any]:
        """Create a new temporary email address on TempMail.Plus.
        
        Uses the exact random name generator and picks a random domain from the dropdown.

        Args:
            clean: Kept for interface backward compatibility.
            domain: Optional explicit domain override. If None, picks randomly from dropdown.

        Returns:
            dict with 'address', 'name', 'domain', and 'expires' timestamp (ms).
        """
        # Ensure domain list is refreshed or populated
        if not self.domains:
            self.domains = fetch_live_domains()

        selected_domain = domain if (domain and domain in self.domains) else random.choice(self.domains)
        name = get_random_pre()
        email = f"{name}@{selected_domain}"

        self.current_email = email
        self.current_name = name
        self.current_domain = selected_domain

        return {
            "address": email,
            "name": name,
            "domain": selected_domain,
            "expires": int((time.time() + 600) * 1000),  # 10 min default in ms
        }

    def create_clean_inbox(self) -> Dict[str, Any]:
        """Create a polished inbox with clean format (alias for create_inbox)."""
        return self.create_inbox(clean=True)

    def get_messages(self, email_or_local: str) -> List[Dict[str, Any]]:
        """Fetch all messages for an inbox from TempMail.Plus."""
        email = self._normalize_email(email_or_local)
        url = f"{self.api_base}/api/mails?email={urllib.parse.quote(email)}&first_id=0&epin="
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("result"):
                    return data.get("mail_list", [])
        except Exception as e:
            print(f"[!] Warning: TempMail.Plus fetch failed: {e}")
        return []

    def get_mail_detail(self, email_or_local: str, mail_id: Any) -> Optional[Dict[str, Any]]:
        """Fetch full content of a specific message by mail_id."""
        email = self._normalize_email(email_or_local)
        url = f"{self.api_base}/api/mails/{mail_id}?email={urllib.parse.quote(email)}&epin="
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("result"):
                    return data
        except Exception as e:
            print(f"[!] Warning: TempMail.Plus detail fetch failed: {e}")
        return None

    def get_latest_code(self, email_or_local: str) -> Optional[str]:
        """Check for incoming emails and extract the OTP verification code.
        
        Returns:
            The extracted OTP code string if found, else None.
        """
        email = self._normalize_email(email_or_local)
        messages = self.get_messages(email)
        if not messages:
            return None

        # Inspect latest message first
        latest = messages[0]
        subject = latest.get("subject", "")
        code = extract_otp_code(subject)
        if code:
            return code

        # If subject doesn't have the code, inspect mail body
        mail_id = latest.get("mail_id")
        if mail_id:
            detail = self.get_mail_detail(email, mail_id)
            if detail:
                text = detail.get("text", "")
                code = extract_otp_code(text)
                if code:
                    return code

                html = detail.get("html", "")
                code = extract_otp_code(html)
                if code:
                    return code

        return None

    def wait_for_otp(
        self,
        email_or_local: str,
        timeout: int = 90,
        poll_interval: float = 2.0,
        log_callback: Optional[Any] = None,
    ) -> Optional[str]:
        """Poll the TempMail.Plus inbox until an OTP code arrives or timeout is reached."""
        email = self._normalize_email(email_or_local)
        start_time = time.time()
        attempt = 1

        while time.time() - start_time < timeout:
            code = self.get_latest_code(email)
            if code:
                if log_callback:
                    log_callback(f"[+] Received OTP code: {code}")
                return code

            if log_callback:
                elapsed = int(time.time() - start_time)
                log_callback(f"[*] Waiting for OTP on {email}... ({elapsed}s elapsed, attempt {attempt})")

            time.sleep(poll_interval)
            attempt += 1

        return None

    def delete_inbox(self, email_or_local: str) -> bool:
        """Destroy/delete all emails for this address on TempMail.Plus."""
        email = self._normalize_email(email_or_local)
        url = f"{self.api_base}/api/mails/?email={urllib.parse.quote(email)}&first_id=0&epin="
        req = urllib.request.Request(url, headers=self._headers(), method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return bool(data.get("result"))
        except Exception:
            return False
