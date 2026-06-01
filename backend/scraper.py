import asyncio
import logging
import re
import ssl
from datetime import datetime, timezone
from typing import Optional
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


async def fetch_url(session: aiohttp.ClientSession, url: str, timeout: int = 30) -> Optional[str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            return await resp.text() if resp.status == 200 else None
    except Exception as e:
        logger.warning(f"fetch failed: {url[:60]}... {e}")
        return None


async def scrape_arxiv(max_results: int = 100) -> list[dict]:
    cats = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:cs.NE+OR+cat:cs.RO+OR+cat:stat.ML"
    url = f"https://export.arxiv.org/api/query?search_query={cats}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        text = await fetch_url(session, url, timeout=60)

    if not text:
        logger.warning("ArXiv returned no data")
        return []

    feed = feedparser.parse(text)
    papers = []
    for entry in feed.entries:
        try:
            pub_date = dateparser.parse(entry.published).replace(tzinfo=timezone.utc) if hasattr(entry, "published") else datetime.now(timezone.utc)
            arxiv_cats = []
            if hasattr(entry, "arxiv_primary_category"):
                arxiv_cats.append(entry.arxiv_primary_category["term"])
            if hasattr(entry, "tags"):
                arxiv_cats.extend(t["term"] for t in entry.tags if "term" in t)
            primary_cat = arxiv_cats[0] if arxiv_cats else "cs.AI"
            papers.append({
                "title": entry.title.replace("\n", " ").strip(),
                "abstract": entry.summary.replace("\n", " ").strip() if hasattr(entry, "summary") else "",
                "category": CATEGORY_MAP.get(primary_cat, "AI"),
                "source": "arxiv",
                "source_url": entry.link if hasattr(entry, "link") else "",
                "published": pub_date,
            })
        except Exception:
            continue

    logger.info(f"ArXiv: {len(papers)} papers")
    return papers


async def scrape_huggingface_papers(count: int = 30) -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        html = await fetch_url(session, "https://huggingface.co/papers")

    if not html:
        logger.warning("HuggingFace returned no data")
        return []

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article") or soup.select("a[href*='/papers/']")
    papers, seen = [], set()

    for article in articles[:count]:
        try:
            title_el = article.select_one("h3, h2, [class*='title']") or article
            link_el = article if article.name == "a" else article.select_one("a[href]")
            title = (title_el.get_text(strip=True) or "")[:300]
            href = link_el.get("href", "") if link_el else ""
            if not title or not href or title in seen:
                continue
            seen.add(title)
            papers.append({
                "title": title,
                "abstract": "",
                "category": "AI",
                "source": "huggingface",
                "source_url": f"https://huggingface.co{href}" if href.startswith("/") else href,
                "published": datetime.now(timezone.utc),
            })
        except Exception:
            continue

    logger.info(f"HuggingFace: {len(papers)} papers")
    return papers


async def scrape_techcrunch_ai(articles_count: int = 20) -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        html = await fetch_url(session, "https://techcrunch.com/category/artificial-intelligence/")

    if not html:
        logger.warning("TechCrunch returned no data")
        return []

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article") or soup.select("a[href*='techcrunch.com']")
    results, seen = [], set()

    for article in articles[:articles_count]:
        try:
            title_el = article.select_one("h2, h3, [class*='title'], [class*='headline']") or article
            link_el = article if article.name == "a" else article.select_one("a[href]")
            summary_el = article.select_one("p, [class*='excerpt'], [class*='summary']")
            title = (title_el.get_text(strip=True) or "")[:300]
            href = link_el.get("href", "") if link_el else ""
            if not title or not href or title in seen:
                continue
            seen.add(title)
            results.append({
                "title": title,
                "abstract": (summary_el.get_text(strip=True) if summary_el else "")[:500],
                "category": "AI Industry",
                "source": "techcrunch",
                "source_url": href,
                "published": datetime.now(timezone.utc),
            })
        except Exception:
            continue

    logger.info(f"TechCrunch: {len(results)} articles")
    return results


async def run_all_scrapers() -> dict:
    arxiv_task = scrape_arxiv(100)
    hf_task = scrape_huggingface_papers(30)
    tc_task = scrape_techcrunch_ai(20)

    results = await asyncio.gather(arxiv_task, hf_task, tc_task, return_exceptions=True)

    papers, sources_scanned = [], []
    for name, result in zip(["arxiv", "huggingface", "techcrunch"], results):
        if isinstance(result, Exception):
            logger.error(f"{name} failed: {result}")
        elif result:
            papers.extend(result)
            sources_scanned.append(name)

    return {"papers": papers, "sources": sources_scanned}
