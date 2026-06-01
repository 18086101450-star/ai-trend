import asyncio
import logging
import re
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


async def fetch_url(session: aiohttp.ClientSession, url: str, timeout: int = 30) -> Optional[str]:
    for attempt in range(2):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning(f"HTTP {resp.status} for {url}")
                return None
        except Exception as e:
            if "SSL" in str(e) and attempt == 0:
                logger.warning(f"SSL error for {url}, retrying with SSL verification disabled")
                return await fetch_url_fallback(url, timeout)
            logger.error(f"Error fetching {url}: {e}")
            return None
    return None


async def fetch_url_fallback(url: str, timeout: int = 30) -> Optional[str]:
    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
        except Exception as e:
            logger.error(f"Fallback fetch error for {url}: {e}")
            return None


async def scrape_arxiv(session: aiohttp.ClientSession, max_results: int = 200) -> list[dict]:
    categories = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:cs.NE+OR+cat:cs.RO+OR+cat:stat.ML"
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query={categories}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_results}"
    )

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
            category = CATEGORY_MAP.get(primary_cat, "AI")

            papers.append({
                "title": entry.title.replace("\n", " ").strip(),
                "abstract": entry.summary.replace("\n", " ").strip() if hasattr(entry, "summary") else "",
                "category": category,
                "source": "arxiv",
                "source_url": entry.link if hasattr(entry, "link") else "",
                "published": pub_date,
                "authors": [a["name"] for a in entry.authors] if hasattr(entry, "authors") else [],
            })
        except Exception as e:
            logger.warning(f"Error parsing arxiv entry: {e}")
            continue

    logger.info(f"Scraped {len(papers)} papers from ArXiv")
    return papers


async def scrape_huggingface_papers(session: aiohttp.ClientSession, count: int = 50) -> list[dict]:
    url = "https://huggingface.co/papers"
    html = await fetch_url(session, url)
    if not html:
        logger.warning("HuggingFace returned no data")
        return []

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article") or soup.select("div[class*='paper']") or soup.select("a[href*='/papers/']")

    papers = []
    seen = set()

    for article in articles[:count]:
        try:
            title_el = article.select_one("h3, h2, [class*='title']") or article
            link_el = article if article.name == "a" else article.select_one("a[href]")
            title = (title_el.get_text(strip=True) or "")[:300]
            href = link_el.get("href", "") if link_el else ""

            if not title or not href or title in seen:
                continue
            seen.add(title)

            href = f"https://huggingface.co{href}" if href.startswith("/") else href
            papers.append({
                "title": title,
                "abstract": "",
                "category": "AI",
                "source": "huggingface",
                "source_url": href,
                "published": datetime.now(timezone.utc),
            })
        except Exception as e:
            continue

    # try to get abstracts for each paper
    async def fetch_abstract(paper: dict) -> dict:
        if not paper["source_url"]:
            return paper
        html = await fetch_url(session, paper["source_url"], timeout=15)
        if html:
            s = BeautifulSoup(html, "lxml")
            abs_el = s.select_one("div[class*='abstract'], section[class*='abstract'], meta[name='description']")
            if abs_el:
                if abs_el.name == "meta":
                    paper["abstract"] = abs_el.get("content", "")
                else:
                    paper["abstract"] = abs_el.get_text(strip=True)[:1000]
            # try to get category
            cat_el = s.select_one("a[href*='/categories'], span[class*='category']")
            if cat_el:
                paper["category"] = cat_el.get_text(strip=True)
        return paper

    batch = [fetch_abstract(p) for p in papers[:20]]
    papers = await asyncio.gather(*batch)

    logger.info(f"Scraped {len(papers)} papers from HuggingFace")
    return papers


async def scrape_techcrunch_ai(session: aiohttp.ClientSession, articles_count: int = 30) -> list[dict]:
    url = "https://techcrunch.com/category/artificial-intelligence/"
    html = await fetch_url(session, url)
    if not html:
        logger.warning("TechCrunch returned no data")
        return []

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article") or soup.select("div[class*='post']") or soup.select("a[href*='techcrunch.com']")

    results = []
    seen = set()

    for article in articles[:articles_count]:
        try:
            title_el = article.select_one("h2, h3, [class*='title'], [class*='headline']") or article
            link_el = article if article.name == "a" else article.select_one("a[href]")
            summary_el = article.select_one("p, [class*='excerpt'], [class*='summary']")

            title = (title_el.get_text(strip=True) or "")[:300]
            href = link_el.get("href", "") if link_el else ""
            summary = (summary_el.get_text(strip=True) if summary_el else "")[:500]

            if not title or not href or title in seen:
                continue
            seen.add(title)

            results.append({
                "title": title,
                "abstract": summary,
                "category": "AI Industry",
                "source": "techcrunch",
                "source_url": href,
                "published": datetime.now(timezone.utc),
            })
        except Exception:
            continue

    logger.info(f"Scraped {len(results)} articles from TechCrunch")
    return results


async def run_all_scrapers(max_arxiv: int = 200, hf_count: int = 50, tc_count: int = 30) -> dict:
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        arxiv_task = scrape_arxiv(session, max_arxiv)
        hf_task = scrape_huggingface_papers(session, hf_count)
        tc_task = scrape_techcrunch_ai(session, tc_count)

        results = await asyncio.gather(arxiv_task, hf_task, tc_task, return_exceptions=True)

    papers = []
    sources_scanned = []

    for i, (name, result) in enumerate(zip(
        ["arxiv", "huggingface", "techcrunch"], results
    )):
        if isinstance(result, Exception):
            logger.error(f"{name} scraper failed: {result}")
        elif result:
            papers.extend(result)
            sources_scanned.append(name)

    return {"papers": papers, "sources": sources_scanned}
