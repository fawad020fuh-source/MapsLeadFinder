from __future__ import annotations

import logging
import re
import time
from typing import Iterable, List, Optional, Set
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)


class WebsiteCrawler:
    """Fetch and parse business websites while respecting robots.txt."""

    def __init__(self, user_agent: str = "MapsLeadFinder/1.0 (+https://github.com/fawad020fuh-source/MapsLeadFinder)", timeout: float = 20.0, delay_range: tuple[float, float] = (1.0, 3.0)):
        self.user_agent = user_agent
        self.timeout = timeout
        self.delay_range = delay_range

    def _random_delay(self) -> None:
        if not self.delay_range:
            return
        low, high = self.delay_range
        time.sleep(low + (high - low) * 0.5)

    def _robots_allowed(self, url: str) -> bool:
        try:
            parsed = httpx.URL(url)
            robots_url = f"{parsed.scheme}://{parsed.host}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.read()
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def fetch_text(self, url: str) -> str:
        if not url:
            return ""
        if not self._robots_allowed(url):
            logger.warning("robots.txt disallowed access for %s", url)
            return ""
        try:
            self._random_delay()
            headers = {"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.9"}
            with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
                resp = client.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPError as exc:
            logger.warning("Web fetch failed for %s: %s", url, exc)
            return ""

    def get_page_links(self, html: str, base_url: str) -> Set[str]:
        if not html:
            return set()
        soup = BeautifulSoup(html, "lxml")
        links: Set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href:
                continue
            if href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            full_url = urljoin(base_url, href)
            links.add(full_url)
        return links

    def gather_candidate_pages(self, website: str) -> List[str]:
        if not website:
            return []
        normalized = website.rstrip("/")
        candidates = {normalized}
        for suffix in ["/contact", "/contact-us", "/about", "/about-us"]:
            candidates.add(normalized + suffix)
        return sorted(candidates)


__all__ = ["WebsiteCrawler"]
