"""HTTP client with retry, back-off and per-host rate limiting.

The original study pipeline delegated all of this to an internal job scheduler;
the released package keeps the behaviour but drops the dependency so the script
can run on a plain machine.  Proxy settings are read from the usual
``HTTP_PROXY`` / ``HTTPS_PROXY`` environment variables.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Optional

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 LiSkill/0.1 (license research)"
)


@dataclass
class RateLimit:
    """``calls`` requests per ``seconds`` (the ``rate_limit`` tuple of a platform)."""

    calls: int = 1
    seconds: float = 2.0
    _last: float = field(default=0.0, repr=False)

    def wait(self) -> None:
        if self.calls <= 0 or self.seconds <= 0:
            return
        interval = self.seconds / self.calls
        elapsed = time.monotonic() - self._last
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last = time.monotonic()


class HttpClient:
    """Minimal JSON / HTML fetcher."""

    def __init__(
        self,
        rate_limit: Optional[RateLimit] = None,
        retries: int = 3,
        timeout: int = 30,
        user_agent: str = DEFAULT_USER_AGENT,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.rate_limit = rate_limit or RateLimit()
        self.retries = retries
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent, "Accept": "*/*"}
        if headers:
            self.headers.update(headers)

    def get(self, url: str, params: Optional[Dict[str, object]] = None, headers: Optional[Dict[str, str]] = None) -> str:
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}{'&' if '?' in url else '?'}{query}"
        return self._request(url, method="GET", headers=headers)

    def post(self, url: str, payload: Dict[str, object], headers: Optional[Dict[str, str]] = None) -> str:
        merged = {"Content-Type": "application/json"}
        merged.update(headers or {})
        return self._request(url, method="POST", body=json.dumps(payload).encode("utf-8"), headers=merged)

    # ------------------------------------------------------------------ internals
    def _request(
        self,
        url: str,
        method: str = "GET",
        body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        merged = dict(self.headers)
        merged.update(headers or {})
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            self.rate_limit.wait()
            request = urllib.request.Request(url, data=body, headers=merged, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(1.5 ** attempt)
        raise RuntimeError(f"request failed after {self.retries + 1} attempts: {url} ({last_error})")
