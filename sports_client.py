"""Клиент для ленты новостей Sports.ru с пагинацией по времени."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from html import unescape
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.sports.ru"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

MONTHS_RU = {
    "янв": 1,
    "января": 1,
    "фев": 2,
    "февраля": 2,
    "мар": 3,
    "марта": 3,
    "апр": 4,
    "апреля": 4,
    "май": 5,
    "мая": 5,
    "июн": 6,
    "июня": 6,
    "июл": 7,
    "июля": 7,
    "авг": 8,
    "августа": 8,
    "сен": 9,
    "сентября": 9,
    "окт": 10,
    "октября": 10,
    "ноя": 11,
    "ноября": 11,
    "дек": 12,
    "декабря": 12,
}

FILTER_MAP = {
    "news": ("filters[3]", "news"),
    "article": ("filters[4]", "article"),
    "blog": ("filters[5]", "blog"),
    "main": ("filters[1]", "main"),
}

TAG_URL_RE = re.compile(
    r"^https?://(?:www\.)?sports\.ru/"
    r"(?P<section>[^/]+)/"
    r"(?P<kind>person|club|team|tournament|coach)/"
    r"(?P<slug>[^/?#]+)/?$"
)

KIND_LABELS = {
    "person": "человек",
    "club": "клуб",
    "team": "команда",
    "tournament": "турнир",
    "coach": "тренер",
}


@dataclass
class TagInfo:
    tag_id: str
    title: str
    url: str
    kind: str | None = None
    section: str | None = None


@dataclass
class NewsItem:
    title: str
    url: str
    published: datetime
    comments: int | None = None
    source: str | None = None


class SportsClient:
    def __init__(self, timeout: float = 25.0) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self.timeout = timeout

    def resolve_tag(self, raw: str) -> TagInfo:
        tag, _alts = self.resolve_tag_with_alts(raw)
        return tag

    def resolve_tag_with_alts(self, raw: str) -> tuple[TagInfo, list[TagInfo]]:
        raw = (raw or "").strip()
        if not raw:
            raise ValueError("Укажите название тега")

        if raw.isdigit():
            tag = TagInfo(
                tag_id=raw,
                title=f"Тег {raw}",
                url=f"{BASE}/stat/tags/other/lenta/{raw}.html",
            )
            return tag, []

        if self._looks_like_url(raw):
            return self._resolve_from_url(raw), []

        primary, alts = self._search_tag_candidates(raw)
        if not primary:
            raise ValueError(
                f"Тег «{raw}» не найден. Попробуйте другое написание, "
                "например «Этери Тутберидзе» или «Спартак»."
            )
        tag = self._resolve_from_url(primary.url, title_hint=primary.title)
        resolved_alts: list[TagInfo] = []
        for alt in alts[:8]:
            if alt.url == tag.url:
                continue
            resolved_alts.append(alt)
        return tag, resolved_alts

    def _looks_like_url(self, raw: str) -> bool:
        value = raw.strip()
        return bool(
            re.match(r"^https?://", value, re.I)
            or value.startswith("//")
            or value.startswith("/")
            or "sports.ru/" in value.lower()
        )

    def _resolve_from_url(self, raw: str, title_hint: str | None = None) -> TagInfo:
        url = self._normalize_url(raw)
        html = self._get(url)
        tag_id = self._extract_tag_id(html, url)
        if not tag_id:
            raise ValueError(
                "Не удалось определить тег по ссылке. "
                "Проверьте адрес страницы на Sports.ru."
            )
        title = self._extract_title(html) or title_hint or url
        meta = TAG_URL_RE.match(url if url.endswith("/") else url + "/")
        return TagInfo(
            tag_id=tag_id,
            title=title,
            url=url,
            kind=meta.group("kind") if meta else None,
            section=meta.group("section") if meta else None,
        )

    def _search_tag_candidates(self, query: str) -> tuple[TagInfo | None, list[TagInfo]]:
        resp = self.session.get(
            f"{BASE}/search/",
            params={"query": query},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        block = soup.select_one(".search-result")
        if not block:
            return None, []

        candidates: list[TagInfo] = []
        seen: set[str] = set()
        for a in block.select("a[href]"):
            href = urljoin(BASE, a.get("href") or "")
            href_n = href if href.endswith("/") else href + "/"
            meta = TAG_URL_RE.match(href_n)
            if not meta:
                continue
            if href_n in seen:
                continue
            seen.add(href_n)
            title = clean_text(a.get_text(" ", strip=True))
            if not title:
                continue
            candidates.append(
                TagInfo(
                    tag_id="",
                    title=title,
                    url=href_n,
                    kind=meta.group("kind"),
                    section=meta.group("section"),
                )
            )

        if not candidates:
            return None, []

        primary = candidates[0]
        q_norm = normalize_name(query)
        alts = [
            c
            for c in candidates[1:]
            if name_score(q_norm, normalize_name(c.title)) >= 50
        ]
        # If a later candidate is an exact title match and primary is not, prefer it.
        for c in candidates:
            if normalize_name(c.title) == q_norm:
                primary = c
                alts = [x for x in candidates if x.url != primary.url and name_score(q_norm, normalize_name(x.title)) >= 50]
                break
        return primary, alts

    def fetch_news(
        self,
        tag_id: str,
        date_from: date,
        date_to: date,
        content_types: Iterable[str] | None = None,
        max_pages: int = 80,
    ) -> list[NewsItem]:
        if date_from > date_to:
            raise ValueError("Дата «с» не может быть позже даты «по»")

        types = list(content_types or ["news"])
        end_exclusive = datetime.combine(date_to + timedelta(days=1), time.min)
        start = datetime.combine(date_from, time.min)
        ts = int(end_exclusive.replace(tzinfo=timezone.utc).timestamp())

        collected: list[NewsItem] = []
        seen_urls: set[str] = set()
        reached_before_range = False

        for _ in range(max_pages):
            html = self._get_lenta(tag_id, ts, types)
            if not html.strip():
                break

            items, next_ts = self._parse_lenta(html)
            if not items:
                break

            for item in items:
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)

                if item.published >= end_exclusive:
                    continue
                if item.published < start:
                    reached_before_range = True
                    continue
                collected.append(item)

            if reached_before_range:
                break
            if next_ts is None or next_ts >= ts:
                break
            ts = next_ts

        collected.sort(key=lambda x: x.published, reverse=True)
        return collected

    def _get(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def _get_lenta(self, tag_id: str, ts: int, content_types: list[str]) -> str:
        params = [f"ts={ts}", "no_controls=1"]
        for key in content_types:
            if key in FILTER_MAP:
                name, value = FILTER_MAP[key]
                params.append(f"{name}={value}")
        url = f"{BASE}/stat/tags/other/lenta/{tag_id}.html?" + "&".join(params)
        resp = self.session.get(
            url,
            timeout=self.timeout,
            headers={"Referer": f"{BASE}/", "X-Requested-With": "XMLHttpRequest"},
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def _normalize_url(self, raw: str) -> str:
        if raw.startswith("//"):
            raw = "https:" + raw
        if not re.match(r"^https?://", raw, re.I):
            raw = urljoin(BASE + "/", raw.lstrip("/"))
        parsed = urlparse(raw)
        if "sports.ru" not in parsed.netloc:
            raise ValueError("Поддерживаются только ссылки на sports.ru")
        return raw

    def _extract_tag_id(self, html: str, url: str) -> str | None:
        patterns = [
            r'data-tag_id="(\d+)"',
            r'"page_id"\s*:\s*(\d+)',
            r"page_id\s*:\s*(\d+)",
            r"/stat/tags/other/(?:lenta|news)/(\d+)\.html",
            r"/tags/other/lenta/(\d+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return m.group(1)

        m = re.search(r"/tags/(\d+)/?", url)
        if m:
            return m.group(1)
        return None

    def _extract_title(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            title = re.sub(r"\s*[—\-|:].*$", "", title).strip()
            return title or None
        return None

    def _parse_lenta(self, html: str) -> tuple[list[NewsItem], int | None]:
        soup = BeautifulSoup(html, "lxml")
        items: list[NewsItem] = []

        for block in soup.select("div.nl-item"):
            day_el = block.select_one(":scope > div > span.date")
            if not day_el:
                day_el = block.find("span", class_="date")
            day_text = day_el.get_text(strip=True) if day_el else ""
            day = parse_ru_day(day_text)
            if not day:
                continue

            source_el = block.select_one("a.nickname")
            source = source_el.get_text(strip=True) if source_el else None

            for p in block.find_all("p"):
                link = p.select_one("a.short-text")
                if not link or not link.get("href"):
                    continue
                time_el = p.select_one("span.date")
                hhmm = time_el.get_text(strip=True) if time_el else "00:00"
                published = combine_day_time(day, hhmm)
                href = urljoin(BASE, link["href"])
                title = clean_text(link.get_text(" ", strip=True))
                comments = None
                comment_link = p.find("a", href=re.compile(r"#comments"))
                if comment_link:
                    raw = comment_link.get_text(strip=True)
                    if raw.isdigit():
                        comments = int(raw)
                items.append(
                    NewsItem(
                        title=title,
                        url=href,
                        published=published,
                        comments=comments,
                        source=source,
                    )
                )

        next_ts = None
        more = soup.select_one("div.c-show-more[data-url]")
        if more and more.get("data-url"):
            qs = parse_qs(urlparse(more["data-url"]).query)
            if "ts" in qs and qs["ts"]:
                try:
                    next_ts = int(qs["ts"][0])
                except ValueError:
                    next_ts = None
        return items, next_ts


def parse_ru_day(text: str) -> date | None:
    text = (text or "").strip().lower().replace("\xa0", " ")
    if not text:
        return None
    m = re.match(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", text)
    if not m:
        return None
    day = int(m.group(1))
    month = MONTHS_RU.get(m.group(2))
    year = int(m.group(3))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def combine_day_time(day: date, hhmm: str) -> datetime:
    m = re.match(r"(\d{1,2}):(\d{2})", (hhmm or "").strip())
    hour = int(m.group(1)) if m else 0
    minute = int(m.group(2)) if m else 0
    return datetime(day.year, day.month, day.day, hour, minute)


def clean_text(text: str) -> str:
    text = unescape(text or "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name(text: str) -> str:
    text = clean_text(text).lower().replace("ё", "е")
    text = re.sub(r"[\"«»„“”]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def name_score(query: str, title: str) -> int:
    if not query or not title:
        return 0
    if query == title:
        return 100
    if query in title or title in query:
        return 80
    q_tokens = set(query.split())
    t_tokens = set(title.split())
    if not q_tokens or not t_tokens:
        return 0
    overlap = len(q_tokens & t_tokens)
    if overlap:
        return int(55 + 40 * overlap / max(len(q_tokens), len(t_tokens)))
    return 0


def format_tag_meta(tag: TagInfo) -> str:
    parts: list[str] = []
    if tag.kind and tag.kind in KIND_LABELS:
        parts.append(KIND_LABELS[tag.kind])
    if tag.section:
        parts.append(tag.section)
    return " · ".join(parts)
