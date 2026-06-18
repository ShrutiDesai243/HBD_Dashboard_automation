import random
from scrapy import signals


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
]


class RotateUserAgentMiddleware:
    """Rotates User-Agent on every request."""

    def __init__(self, user_agents):
        self.user_agents = user_agents or DEFAULT_USER_AGENTS

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getlist("USER_AGENTS"))

    def process_request(self, request):
        request.headers["User-Agent"] = random.choice(self.user_agents)


class FlipkartHeadersMiddleware:
    """
    Injects browser-like headers that Flipkart expects.
    Without these, Flipkart returns 403.
    """

    HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language":  "en-IN,en;q=0.9",
        "Accept-Encoding":  "gzip, deflate, br",
        "Connection":       "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":   "document",
        "Sec-Fetch-Mode":   "navigate",
        "Sec-Fetch-Site":   "same-origin",
        "Sec-Fetch-User":   "?1",
        "Cache-Control":    "max-age=0",
    }

    def process_request(self, request):
        for key, val in self.HEADERS.items():
            request.headers.setdefault(key, val)
