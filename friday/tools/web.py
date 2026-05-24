"""
Web tools — search, fetch pages, and global news briefings.
"""

import asyncio
import html
import re
import webbrowser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

SEED_FEEDS = [
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://www.aljazeera.com/xml/rss/all.xml'
]

FINANCE_SEED_FEEDS = [
    'https://www.cnbc.com/id/10000664/device/rss/rss.html',       # CNBC Finance
    'https://feeds.bloomberg.com/markets/news.rss',                # Bloomberg Markets
    'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best',  # Reuters
    'https://feeds.marketwatch.com/marketwatch/topstories/',       # MarketWatch
    'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',  # NYT Business
]


class _DuckDuckGoParser(HTMLParser):
    """Small parser for DuckDuckGo's lightweight HTML results page."""

    def __init__(self) -> None:
        super().__init__()
        self.results = []
        self._active_title = None
        self._active_snippet = False
        self._text = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = attr.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._active_title = attr.get("href", "")
            self._text = []
        elif "result__snippet" in classes:
            self._active_snippet = True
            self._text = []

    def handle_data(self, data):
        if self._active_title is not None or self._active_snippet:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._active_title is not None:
            title = _clean_text(" ".join(self._text))
            if title:
                self.results.append({"title": title, "url": _normalize_ddg_url(self._active_title), "snippet": ""})
            self._active_title = None
            self._text = []
        elif self._active_snippet:
            snippet = _clean_text(" ".join(self._text))
            if snippet and self.results:
                self.results[-1]["snippet"] = snippet
            self._active_snippet = False
            self._text = []


def _clean_text(text: str) -> str:
    text = html.unescape(re.sub(r"\s+", " ", text or "")).strip()
    return text


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return _clean_text(text)


def _normalize_ddg_url(url: str) -> str:
    if url.startswith("//"):
        url = f"https:{url}"
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url


def _validate_web_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only full http or https URLs are supported.")
    return parsed.geturl()

async def fetch_and_parse_feed(client, url):
    """Helper function to handle a single feed request and parse its XML."""
    try:
        response = await client.get(url, headers={'User-Agent': 'Friday-AI/1.0'}, timeout=5.0)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        # Extract source name from URL (e.g., 'BBC' or 'NYTIMES')
        source_name = url.split('.')[1].upper()
        
        feed_items = []
        # Get top 5 items per feed
        items = root.findall(".//item")[:5]
        for item in items:
            title = item.findtext("title")
            description = item.findtext("description")
            link = item.findtext("link")
            
            if description:
                description = re.sub('<[^<]+?>', '', description).strip()

            feed_items.append({
                "source": source_name,
                "title": title,
                "summary": description[:200] + "..." if description else "",
                "link": link
            })
        return feed_items
    except Exception:
        # If one feed fails, return an empty list so others can still succeed
        return []

def register(mcp):

    @mcp.tool()
    async def get_world_news() -> str:
        """
        Fetches the latest global headlines from major news outlets simultaneously.
        Use this when the user asks 'What's going on in the world?' or for recent events.
        """
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            # 1. Create a list of 'tasks' (one for each URL)
            tasks = [fetch_and_parse_feed(client, url) for url in SEED_FEEDS]
            
            # 2. Fire them all at once and wait for the results
            # results will be a list of lists: [[news from bbc], [news from nyt], ...]
            results_of_lists = await asyncio.gather(*tasks)
            
            # 3. Flatten the list of lists into a single list of articles
            all_articles = [item for sublist in results_of_lists for item in sublist]

        if not all_articles:
            return "The global news grid is unresponsive, sir. I'm unable to pull headlines."

        # 4. Format the final briefing
        report = ["### GLOBAL NEWS BRIEFING (LIVE)\n"]
        # Limit to top 12 items so the AI doesn't get overwhelmed
        for entry in all_articles[:12]:
            report.append(f"**[{entry['source']}]** {entry['title']}")
            report.append(f"{entry['summary']}")
            report.append(f"Link: {entry['link']}\n")

        return "\n".join(report)

    @mcp.tool()
    async def get_world_finance_news() -> str:
        """
        Fetches the latest finance and market headlines from major financial outlets simultaneously.
        Use this when the user asks about finance news, market updates, or economic developments.
        """

        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            tasks = [fetch_and_parse_feed(client, url) for url in FINANCE_SEED_FEEDS]
            results_of_lists = await asyncio.gather(*tasks)
            all_articles = [item for sublist in results_of_lists for item in sublist]

        if not all_articles:
            return "The financial feeds are unresponsive right now, sir. I can't pull market headlines."

        report = ["### FINANCE BRIEFING (LIVE)\n"]
        for entry in all_articles[:12]:
            report.append(f"**[{entry['source']}]** {entry['title']}")
            report.append(f"{entry['summary']}")
            report.append(f"Link: {entry['link']}\n")

        return "\n".join(report)

    @mcp.tool()
    async def search_web(query: str, max_results: int = 5) -> str:
        """
        Search the web and return source-linked results.
        Use this for current facts, unfamiliar topics, or anything likely to have changed recently.
        """
        query = _clean_text(query)
        if not query:
            return "Search query is empty."

        max_results = max(1, min(max_results, 8))
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            response = await client.get(
                "https://duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Friday-AI/1.0"},
            )
            response.raise_for_status()

        parser = _DuckDuckGoParser()
        parser.feed(response.text)
        results = parser.results[:max_results]
        if not results:
            return f"No useful search results found for: {query}"

        lines = [f"SEARCH RESULTS for: {query}"]
        for index, result in enumerate(results, 1):
            lines.append(f"{index}. {result['title']}")
            if result["snippet"]:
                lines.append(f"   {result['snippet'][:300]}")
            lines.append(f"   Source: {result['url']}")
        return "\n".join(lines)

    @mcp.tool()
    async def fetch_url(url: str) -> str:
        """Fetch readable text content from a public http/https URL."""
        url = _validate_web_url(url)
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" in content_type:
                text = _strip_html(response.text)
            else:
                text = _clean_text(response.text)
            return text[:6000]

    @mcp.tool()
    async def open_url(url: str) -> str:
        """
        Open a public http/https URL in the user's default browser.
        Use only when the user explicitly asks to open, show, or pull up a page.
        """
        url = _validate_web_url(url)
        try:
            webbrowser.open(url)
            return f"Opened: {url}"
        except Exception as exc:
            return f"I couldn't open that page: {exc}"
    
    @mcp.tool()
    async def open_world_monitor() -> str:
        """
        Opens the World Monitor dashboard (worldmonitor.app) in the system's web browser.
        Use this when the user wants a visual overview of global events or a real-time map.
        """
        url = "https://worldmonitor.app/"
        
        try:
            webbrowser.open(url)
            return "Displaying the World Monitor on your primary screen now, sir."
        except Exception as e:
            return f"I'm unable to initialize the visual monitor: {str(e)}"

    @mcp.tool()
    async def open_finance_world_monitor() -> str:
        """
        Opens the Finance World Monitor dashboard (finance.worldmonitor.app) in the system's web browser.
        Use this when the user wants a visual overview of global financial markets and trends.
        """
        url = "https://finance.worldmonitor.app/"

        try:
            webbrowser.open(url)
            return "Displaying the Finance World Monitor on your primary screen now, sir."
        except Exception as e:
            return f"I'm unable to initialize the finance monitor: {str(e)}"
