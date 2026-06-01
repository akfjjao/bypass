import sqlite3
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
from bypass_engine import BypassEngine

app = FastAPI(title="LuminaBypass API", description="High-performance URL Shortener Bypassing Engine")

# Setup Directories & Templates
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")

# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            bypassed_url TEXT,
            strategy TEXT,
            time_taken REAL,
            hops TEXT,
            success INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_to_history(original_url: str, bypassed_url: str, strategy: str, time_taken: float, hops: list, success: bool):
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO history (original_url, bypassed_url, strategy, time_taken, hops, success)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (original_url, bypassed_url, strategy, time_taken, json.dumps(hops), 1 if success else 0))
    conn.commit()
    conn.close()

def get_history_list(limit: int = 20):
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/history")
async def get_history():
    try:
        data = get_history_list()
        # Decode hops from JSON string
        for item in data:
            try:
                item["hops"] = json.loads(item["hops"]) if item["hops"] else []
            except:
                item["hops"] = []
        return JSONResponse(content={"success": True, "history": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


class BypassRequest(BaseModel):
    url: str


@app.post("/api/bypass")
async def api_bypass(req: BypassRequest):
    engine = BypassEngine(headless=config.PLAYWRIGHT_HEADLESS)
    result = await engine.bypass(req.url)
    
    # Save results to DB
    save_to_history(
        original_url=req.url,
        bypassed_url=result.get("bypassed_url"),
        strategy=result.get("strategy"),
        time_taken=result.get("time_taken", 0.0),
        hops=result.get("hops", []),
        success=result.get("success", False)
    )
    
    return JSONResponse(content=result)


@app.websocket("/ws/bypass")
async def websocket_bypass(websocket: WebSocket):
    await websocket.accept()
    engine = BypassEngine(headless=config.PLAYWRIGHT_HEADLESS)
    
    try:
        # Receive target URL payload
        data = await websocket.receive_text()
        req_data = json.loads(data)
        target_url = req_data.get("url")
        
        if not target_url:
            await websocket.send_json({"type": "error", "message": "Missing URL parameter."})
            await websocket.close()
            return
        
        # Define progress updates callback
        async def progress_callback(message: str, status: str):
            await websocket.send_json({
                "type": "progress",
                "message": message,
                "status": status
            })
        
        # Invoke core engine bypass logic
        result = await engine.bypass(target_url, progress_callback=progress_callback)
        
        # Save to SQLite database
        save_to_history(
            original_url=target_url,
            bypassed_url=result.get("bypassed_url"),
            strategy=result.get("strategy"),
            time_taken=result.get("time_taken", 0.0),
            hops=result.get("hops", []),
            success=result.get("success", False)
        )
        
        # Stream final result
        await websocket.send_json({
            "type": "result",
            "result": result
        })
        
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
