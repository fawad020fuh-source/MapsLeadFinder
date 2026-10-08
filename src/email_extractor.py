from __future__ import annotations

import logging
import re
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .crawler import WebsiteCrawler

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class EmailExtractor:
    """Extract and normalize business emails from a website."""

    def __init__(self, crawler: Optional[WebsiteCrawler] = None):
        self.crawler = crawler or WebsiteCrawler()

    @staticmethod
    def _normalize_email(raw: str) -> str:
        value = raw.strip().lower()
        value = re.sub(r"^mailto:\s*", "", value, flags=re.I)
        value = re.sub(r"\s+", "", value)
        value = value.replace("[at]", "@").replace("(at)", "@").replace(" at ", "@")
        value = value.replace("[dot]", ".").replace("(dot)", ".").replace(" dot ", ".")
        value = value.replace("_at_", "@").replace("_dot_", ".")
        value = value.replace("&#64;", "@").replace("&#46;", ".")
        if value.count("@") == 1 and value.count(".") >= 1:
            return value
        return value

    @staticmethod
    def _is_junk(email: str) -> bool:
        if not email or email.count("@") != 1:
            return True
        local, domain = email.split("@", 1)
        if not local or not domain:
            return True
        if len(domain.split(".")) < 2:
            return True
        junk_terms = ("example", "noreply", "no-reply", "no_reply", "sentry", "wixpress", "@localhost", ".png", ".jpg", ".svg", ".gif")
        lowered = email.lower()
        if lowered.startswith("example") or "example@" in lowered or "@example." in lowered:
            return True
        if any(term in lowered for term in junk_terms):
            return True
        if local.lower() in {"noreply", "donotreply"}:
            return True
        return False

    @staticmethod
    def _domain_from_url(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return host

    @staticmethod
    def _is_business_domain_match(email: str, website_url: str) -> bool:
        domain = EmailExtractor._domain_from_url(website_url)
        if not domain:
            return True
        email_domain = email.split("@", 1)[1].lower()
        if email_domain == domain:
            return True
        return email_domain.endswith("." + domain)

    def _collect_standard_matches(self, text: str) -> Set[str]:
        found = set()
        for match in EMAIL_PATTERN.findall(text):
            cleaned = self._normalize_email(match)
            if cleaned and not self._is_junk(cleaned):
                found.add(cleaned)
        return found

    def _collect_obfuscated_matches(self, text: str) -> Set[str]:
        candidates: Set[str] = set()
        normalized = text.lower()
        for pattern in [r"\[[ ]*at[ ]*\]", r"\(at\)", r"\bat\b", r"\[at\]", r"_at_"]:
            normalized = re.sub(pattern, "@", normalized, flags=re.I)
        for pattern in [r"\[[ ]*dot[ ]*\]", r"\(dot\)", r"\bdot\b", r"\[dot\]", r"_dot_"]:
            normalized = re.sub(pattern, ".", normalized, flags=re.I)
        candidates.update(self._collect_standard_matches(normalized))
        return candidates

    def _extract_mailto_links(self, html: str) -> Set[str]:
        matches = set(re.findall(r"mailto:([^\s\"'<>]+)", html, flags=re.I))
        return {self._normalize_email(m) for m in matches if not self._is_junk(self._normalize_email(m))}

    def _extract_text_from_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return " ".join(soup.stripped_strings)

    def extract_from_website(self, website_url: str) -> List[str]:
        """Extract valid email candidates from the business website."""
        if not website_url:
            return []
        pages = self.crawler.gather_candidate_pages(website_url)
        emails: List[str] = []
        seen: Set[str] = set()
        for page in pages:
            html = self.crawler.fetch_text(page)
            if not html:
                continue
            text = self._extract_text_from_html(html)
            candidates = set()
            candidates |= self._extract_mailto_links(html)
            candidates |= self._collect_standard_matches(text)
            candidates |= self._collect_obfuscated_matches(text)
            for candidate in sorted(candidates):
                if self._is_junk(candidate):
                    continue
                if candidate in seen:
                    continue
                if not self._is_business_domain_match(candidate, website_url):
                    continue
                seen.add(candidate)
                emails.append(candidate)
        return emails


__all__ = ["EmailExtractor"]
