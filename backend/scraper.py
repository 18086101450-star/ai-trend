import asyncio
import logging
import re
import ssl
from datetime import datetime, timezone
import feedparser
import aiohttp
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "cs.AI": "AI",
    "cs.LG": "Machine Learning",
    "cs.CL": "NLP",
    "cs.CV": "Computer Vision",
    "cs.NE": "Neural Networks",
    "cs.RO": "Robotics",
    "cs.MA": "Multi-Agent",
    "cs.IR": "Information Retrieval",
    "cs.SE": "Software Engineering",
    "stat.ML": "Machine Learning",
    "cs.MM": "Multimedia",
    "cs.SD": "Sound",
    "cs.HC": "Human-Computer Interaction",
}

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# shared HTTP session for connection reuse across all scrapers
_SHARED_CONNECTOR: aiohttp.TCPConnector | None = None
_SHARED_SESSION: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _SHARED_CONNECTOR, _SHARED_SESSION
    if _SHARED_SESSION is None or _SHARED_SESSION.closed:
        _SHARED_CONNECTOR = aiohttp.TCPConnector(ssl=ssl_ctx, limit=10, limit_per_host=4, ttl_dns_cache=300)
        _SHARED_SESSION = aiohttp.ClientSession(connector=_SHARED_CONNECTOR, headers={"User-Agent": "AITrendsHub/1.0"})
    return _SHARED_SESSION


async def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    session = await _get_session()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            return await resp.text() if resp.status == 200 else None
    except Exception as e:
        logger.warning(f"fetch failed: {url[:60]}... {e}")
        return None


def _parse_arxiv_date(entry) -> datetime:
    if hasattr(entry, "published"):
        try:
            return dateparser.parse(entry.published).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _get_arxiv_categories(entry) -> list[str]:
    cats = []
    if hasattr(entry, "arxiv_primary_category"):
        cats.append(entry.arxiv_primary_category["term"])
    if hasattr(entry, "tags"):
        cats.extend(t["term"] for t in entry.tags if "term" in t)
    return cats


async def scrape_arxiv(max_results: int = 100) -> list[dict]:
    cats = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:cs.NE+OR+cat:cs.RO+OR+cat:stat.ML"
    url = f"https://export.arxiv.org/api/query?search_query={cats}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

    text = await fetch_url(url, timeout=60)

    if not text:
        logger.warning("ArXiv returned no data")
        return []

    feed = feedparser.parse(text)
    papers = []
    append = papers.append
    for entry in feed.entries:
        try:
            primary_cat = _get_arxiv_categories(entry)
            pc = primary_cat[0] if primary_cat else "cs.AI"
            append({
                "title": entry.title.replace("\n", " ").strip(),
                "abstract": entry.summary.replace("\n", " ").strip() if hasattr(entry, "summary") else "",
                "category": CATEGORY_MAP.get(pc, "AI"),
                "source": "arxiv",
                "source_url": entry.link if hasattr(entry, "link") else "",
                "published": _parse_arxiv_date(entry),
            })
        except Exception:
            continue

    logger.info(f"ArXiv: {len(papers)} papers")
    return papers


async def scrape_huggingface_papers(count: int = 30) -> list[dict]:
    html = await fetch_url("https://huggingface.co/papers")

    if not html:
        logger.warning("HuggingFace returned no data")
        return []

    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article") or soup.select("a[href*='/papers/']")
    papers, seen = [], set()
    append = papers.append
    now = datetime.now(timezone.utc)

    for article in articles[:count]:
        try:
            link_el = article if article.name == "a" else article.select_one("a[href]")
            title_el = article.select_one("h3, h2, [class*='title']") or article
            if not link_el:
                continue
            title = (title_el.get_text(strip=True) or "")[:300]
            href = link_el.get("href", "")
            if not title or not href or title in seen:
                continue
            seen.add(title)
            url = f"https://huggingface.co{href}" if href.startswith("/") else href
            append({"title": title, "abstract": "", "category": "AI", "source": "huggingface", "source_url": url, "published": now})
        except Exception:
            continue

    logger.info(f"HuggingFace: {len(papers)} papers")
    return papers


async def scrape_techcrunch_ai(articles_count: int = 20) -> list[dict]:
    html = await fetch_url("https://techcrunch.com/category/artificial-intelligence/")

    if not html:
        logger.warning("TechCrunch returned no data")
        return []

    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article") or soup.select("a[href*='techcrunch.com']")
    results, seen = [], set()
    append = results.append
    now = datetime.now(timezone.utc)

    for article in articles[:articles_count]:
        try:
            title_el = article.select_one("h2, h3, [class*='title'], [class*='headline']") or article
            link_el = article if article.name == "a" else article.select_one("a[href]")
            if not title_el or not link_el:
                continue
            summary_el = article.select_one("p, [class*='excerpt'], [class*='summary']")
            title = (title_el.get_text(strip=True) or "")[:300]
            href = link_el.get("href", "")
            if not title or not href or title in seen:
                continue
            seen.add(title)
            append({
                "title": title,
                "abstract": (summary_el.get_text(strip=True) if summary_el else "")[:500],
                "category": "AI Industry",
                "source": "techcrunch",
                "source_url": href,
                "published": now,
            })
        except Exception:
            continue

    logger.info(f"TechCrunch: {len(results)} articles")
    return results


async def scrape_github_trending(count: int = 15) -> list[dict]:
    html = await fetch_url("https://github.com/trending?since=weekly")

    if not html:
        logger.warning("GitHub trending returned no data")
        return []

    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article.Box-row")
    results, seen = [], set()
    append = results.append
    now = datetime.now(timezone.utc)

    for article in articles[:count]:
        try:
            h2 = article.select_one("h2")
            link = h2.select_one("a") if h2 else None
            if not link:
                continue
            full_name = link.get("href", "").strip("/")
            if not full_name or full_name in seen:
                continue
            seen.add(full_name)

            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""
            lang_el = article.select_one("[itemprop='programmingLanguage']")
            language = lang_el.get_text(strip=True) if lang_el else ""
            stars_el = article.select_one(".d-inline-block.float-sm-right")
            stars = stars_el.get_text(strip=True).strip() if stars_el else "0"

            abstract = f"{description} [{language}] ★{stars}" if language else f"{description} ★{stars}"
            append({
                "title": full_name,
                "abstract": abstract,
                "category": "ML Systems / Efficiency",
                "source": "github",
                "source_url": f"https://github.com/{full_name}",
                "published": now,
            })
        except Exception:
            continue

    logger.info(f"GitHub: {len(results)} trending repos")
    return results


async def run_all_scrapers() -> dict:
    arxiv_task = scrape_arxiv(100)
    hf_task = scrape_huggingface_papers(30)
    tc_task = scrape_techcrunch_ai(20)
    gh_task = scrape_github_trending(15)

    results = await asyncio.gather(arxiv_task, hf_task, tc_task, gh_task, return_exceptions=True)

    papers, sources_scanned = [], set()
    for name, result in zip(["arxiv", "huggingface", "techcrunch", "github"], results):
        if isinstance(result, Exception):
            logger.error(f"{name} failed: {result}")
        elif result:
            papers.extend(result)
            sources_scanned.add(name)

    return {"papers": papers, "sources": sorted(sources_scanned)}
