from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes import chat, checks, data, maps, report, scores

APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="rAIn_check")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

app.include_router(data.router)
app.include_router(checks.router)
app.include_router(scores.router)
app.include_router(maps.router)
app.include_router(report.router)
app.include_router(chat.router)


@app.get("/")
def root():
    return RedirectResponse("/data")
