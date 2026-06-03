import logging
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from collections import defaultdict
from sqlalchemy import select, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import init_db, get_db, async_session
from backend.models import Keyword, TrendPrediction, ScanRecord
from backend.scraper import run_all_scrapers
from backend.analyzer import analyze_papers

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Trends Hub...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down AI Trends Hub...")


app = FastAPI(title="AI Trends Hub", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="frontend")


@app.get("/")
async def serve_index():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "AI Trends Hub API is running"}


# ── API Endpoints ──


@app.get("/api/status")
async def api_status(db: AsyncSession = Depends(get_db)):
    kw_count = await db.scalar(sa_func.count(Keyword.id))
    pred_count = await db.scalar(sa_func.count(TrendPrediction.id))
    last_scan = await db.execute(
        select(ScanRecord).order_by(desc(ScanRecord.started_at)).limit(1)
    )
    last_scan = last_scan.scalar_one_or_none()
    return {
        "status": "ok",
        "keywords_tracked": kw_count or 0,
        "predictions_made": pred_count or 0,
        "last_scan": last_scan.to_dict() if last_scan else None,
    }


@app.get("/api/keywords")
async def get_keywords(
    category: str = Query(None),
    search: str = Query(None),
    source: str = Query(None),
    trending: bool = Query(None),
    emerging: bool = Query(None),
    sort: str = Query("trend_score"),
    limit: int = Query(50),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Keyword)

    if category:
        query = query.where(Keyword.category.ilike(f"%{category}%"))
    if search:
        query = query.where(Keyword.keyword.ilike(f"%{search}%"))
    if source:
        query = query.where(Keyword.source.ilike(f"%{source}%"))
    if trending:
        query = query.where(Keyword.is_trending == True)
    if emerging:
        query = query.where(Keyword.is_emerging == True)

    sort_map = {
        "trend_score": desc(Keyword.trend_score),
        "frequency": desc(Keyword.frequency),
        "newest": desc(Keyword.first_seen),
        "alphabetical": Keyword.keyword,
    }
    query = query.order_by(sort_map.get(sort, desc(Keyword.trend_score)))

    total = await db.scalar(sa_func.count(Keyword.id))
    result = await db.execute(query.offset(offset).limit(limit))
    keywords = result.scalars().all()

    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "keywords": [kw.to_dict() for kw in keywords],
    }


@app.get("/api/keywords/{keyword_id}")
async def get_keyword_detail(keyword_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return kw.to_dict()


@app.get("/api/predictions")
async def get_predictions(
    category: str = Query(None),
    limit: int = Query(20),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    query = select(TrendPrediction).order_by(desc(TrendPrediction.created_at))
    if category:
        query = query.where(TrendPrediction.category.ilike(f"%{category}%"))

    total = await db.scalar(sa_func.count(TrendPrediction.id))
    result = await db.execute(query.offset(offset).limit(limit))
    predictions = result.scalars().all()

    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "predictions": [p.to_dict() for p in predictions],
    }


@app.get("/api/scans")
async def get_scans(limit: int = Query(10), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScanRecord).order_by(desc(ScanRecord.started_at)).limit(limit)
    )
    scans = result.scalars().all()
    return {"scans": [s.to_dict() for s in scans]}


@app.get("/api/keywords/{keyword_id}/history")
async def get_keyword_history(keyword_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    wc = kw.weekly_counts or {}
    timeline = []
    for week in sorted(wc.keys()):
        timeline.append({"week": week, "count": wc[week]})
    return {"keyword": kw.keyword, "weekly_counts": wc, "timeline": timeline}


@app.get("/api/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Keyword.category, sa_func.count(Keyword.id).label("count"))
        .group_by(Keyword.category)
        .order_by(desc("count"))
    )
    rows = result.all()
    return {"categories": [{"name": r.category, "count": r.count} for r in rows]}


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_kw = await db.scalar(sa_func.count(Keyword.id))
    total_pred = await db.scalar(sa_func.count(TrendPrediction.id))
    trending_kw = await db.scalar(
        select(sa_func.count(Keyword.id)).where(Keyword.is_trending == True)
    )
    emerging_kw = await db.scalar(
        select(sa_func.count(Keyword.id)).where(Keyword.is_emerging == True)
    )
    avg_score = await db.scalar(select(sa_func.avg(Keyword.trend_score))) or 0

    # most recent scan
    last_scan = await db.execute(
        select(ScanRecord).order_by(desc(ScanRecord.started_at)).limit(1)
    )
    last_scan = last_scan.scalar_one_or_none()

    return {
        "total_keywords": total_kw or 0,
        "total_predictions": total_pred or 0,
        "trending_keywords": trending_kw or 0,
        "emerging_keywords": emerging_kw or 0,
        "average_trend_score": round(float(avg_score), 4),
        "sources_available": ["arxiv", "huggingface", "techcrunch", "github"],
        "last_scan": last_scan.to_dict() if last_scan else None,
    }


@app.get("/api/trend-timeline")
async def get_trend_timeline(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword.weekly_counts, Keyword.trend_score, Keyword.keyword))
    rows = result.all()

    weekly_agg = defaultdict(lambda: {"count": 0, "score_sum": 0.0, "keywords": set()})
    for row in rows:
        wc = row.weekly_counts or {}
        for week, count in wc.items():
            weekly_agg[week]["count"] += count
            weekly_agg[week]["score_sum"] += row.trend_score or 0
            weekly_agg[week]["keywords"].add(row.keyword)

    timeline = []
    for week in sorted(weekly_agg.keys()):
        agg = weekly_agg[week]
        timeline.append({
            "week": week,
            "keyword_count": len(agg["keywords"]),
            "total_mentions": agg["count"],
            "avg_score": round(agg["score_sum"] / max(len(agg["keywords"]), 1), 4),
        })
    return {"timeline": timeline}


@app.post("/api/scan")
async def trigger_scan(db: AsyncSession = Depends(get_db)):
    # check if a scan is already running
    running = await db.execute(
        select(ScanRecord).where(ScanRecord.status == "running").limit(1)
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A scan is already in progress")

    scan = ScanRecord(status="running")
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    async def run_scan():
        try:
            async with async_session() as session:
                scan_id = scan.id
                scan_obj = await session.get(ScanRecord, scan_id)

                result = await run_all_scrapers()

                papers = result["papers"]
                sources = result["sources"]

                analysis = await analyze_papers(papers, session)

                scan_obj.status = "completed"
                scan_obj.sources_scanned = sources
                scan_obj.keywords_found = analysis["keywords_found"]
                scan_obj.predictions_made = analysis["predictions_made"]
                scan_obj.completed_at = datetime.now(timezone.utc)

                await session.commit()
                logger.info(f"Scan #{scan_id} completed: {analysis['keywords_found']} keywords, {analysis['predictions_made']} predictions")
        except Exception as e:
            logger.error(f"Scan failed: {e}", exc_info=True)
            try:
                async with async_session() as session:
                    scan_obj = await session.get(ScanRecord, scan.id)
                    if scan_obj:
                        scan_obj.status = "failed"
                        scan_obj.error = str(e)
                        scan_obj.completed_at = datetime.now(timezone.utc)
                        await session.commit()
            except Exception:
                pass

    asyncio.create_task(run_scan())

    return {
        "message": "Scan started",
        "scan_id": scan.id,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
