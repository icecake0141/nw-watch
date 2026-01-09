"""Web application for network device monitoring."""
import logging
import math
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from yaml import YAMLError

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared.config import Config
from shared.db import Database
from shared.diff import generate_side_by_side_diff
from webapp.websocket_manager import manager

logger = logging.getLogger(__name__)

app = FastAPI(title="Network Watch")

# Setup templates and static files
templates = Jinja2Templates(directory="webapp/templates")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

DEFAULT_HISTORY_SIZE = 10


@lru_cache(maxsize=1)
def load_config() -> Config:
    """Load config once (cached)."""
    return Config('config.yaml')


def resolve_history_size() -> int:
    """Return configured history size with safe fallback."""
    try:
        return load_config().get_history_size()
    except (FileNotFoundError, PermissionError, YAMLError) as exc:
        logger.warning("Config fallback for history size: %s", exc)
        return DEFAULT_HISTORY_SIZE


def get_db(history_size: int) -> Optional[Database]:
    """Get database connection."""
    db_path = Path('data/current.sqlite3')
    if not db_path.exists():
        return None
    return Database(str(db_path), history_size=history_size)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main page."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/commands")
async def get_commands():
    """Get list of all commands."""
    try:
        config = load_config()
        commands_cfg = config.get_commands()
        if commands_cfg:
            sorted_cmds = sorted(
                commands_cfg,
                key=lambda c: c.get("sort_order", 0)
            )
            return JSONResponse({"commands": [c.get("command_text") for c in sorted_cmds]})
    except (FileNotFoundError, PermissionError, YAMLError) as exc:
        # Fallback to database if config is missing or unreadable
        logger.warning("Config fallback for /api/commands: %s", exc)

    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"commands": []})

    try:
        commands = db.get_all_commands()
        return JSONResponse({"commands": commands})
    finally:
        db.close()


@app.get("/api/devices")
async def get_devices():
    """Get list of all devices."""
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"devices": []})
    
    try:
        devices = db.get_all_devices()
        return JSONResponse({"devices": devices})
    finally:
        db.close()


@app.get("/api/runs/{command}")
async def get_runs(command: str, device: Optional[str] = None, limit: int = DEFAULT_HISTORY_SIZE):
    """Get command runs for a specific command."""
    try:
        cfg = load_config()
        limit = cfg.get_history_size()
    except (FileNotFoundError, PermissionError, YAMLError) as exc:
        logger.warning("Config fallback for /api/runs: %s", exc)

    db = get_db(history_size=limit)
    if not db:
        return JSONResponse({"runs": {}})
    
    try:
        devices = [device] if device else db.get_all_devices()
        result = {}
        
        for dev in devices:
            runs = db.get_latest_runs(dev, command, limit=limit, include_filtered=False)
            result[dev] = runs
        
        return JSONResponse({"runs": result})
    finally:
        db.close()


@app.get("/api/diff/history")
async def get_history_diff(command: str, device: str):
    """Get diff between latest and previous run."""
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)
    
    try:
        runs = db.get_latest_runs(device, command, limit=2, include_filtered=False)
        
        if len(runs) < 2:
            return JSONResponse({
                "diff": "Not enough history for comparison",
                "has_diff": False,
                "diff_format": "text"
            })
        
        latest = runs[0]
        previous = runs[1]
        
        previous_text = previous.get('output_text', '')
        latest_text = latest.get('output_text', '')
        diff = generate_side_by_side_diff(
            previous_text,
            latest_text,
            label_a="Previous",
            label_b="Latest"
        )
        has_diff = previous_text != latest_text
        
        return JSONResponse({
            "diff": diff,
            "diff_format": "html",
            "has_diff": has_diff,
            "latest_ts": latest['ts_epoch'],
            "previous_ts": previous['ts_epoch']
        })
    finally:
        db.close()


@app.get("/api/diff/devices")
async def get_device_diff(command: str, device_a: str, device_b: str):
    """Get diff between two devices for the same command."""
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)
    
    try:
        run_a = db.get_latest_run(device_a, command, include_filtered=False)
        run_b = db.get_latest_run(device_b, command, include_filtered=False)
        
        if not run_a or not run_b:
            return JSONResponse({
                "diff": "Data not available for both devices",
                "has_diff": False,
                "diff_format": "text"
            })
        
        run_a_text = run_a.get('output_text', '')
        run_b_text = run_b.get('output_text', '')
        diff = generate_side_by_side_diff(
            run_a_text,
            run_b_text,
            label_a=device_a,
            label_b=device_b
        )
        has_diff = run_a_text != run_b_text
        
        return JSONResponse({
            "diff": diff,
            "diff_format": "html",
            "has_diff": has_diff,
            "device_a_ts": run_a['ts_epoch'],
            "device_b_ts": run_b['ts_epoch']
        })
    finally:
        db.close()


@app.get("/api/ping")
async def get_ping_status(window_seconds: int = 60):
    """Get ping status for all devices."""
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"ping_status": {}})
    
    try:
        devices = db.get_all_devices()
        current_ts = int(time.time())
        since_ts = current_ts - window_seconds
        
        result = {}
        for device in devices:
            samples = db.get_ping_samples(device, since_ts)
            
            # Calculate stats
            total = len(samples)
            successful = sum(1 for s in samples if s['ok'])
            
            if total > 0:
                success_rate = (successful / total) * 100
                avg_rtt = None
                if successful > 0:
                    rtts = [s['rtt_ms'] for s in samples if s['ok'] and s['rtt_ms'] is not None]
                    if rtts:
                        avg_rtt = sum(rtts) / len(rtts)
                # Build timeline (oldest -> newest)
                samples_by_ts = {s['ts_epoch']: s for s in samples}
                timeline = []
                for offset in range(window_seconds - 1, -1, -1):
                    ts = current_ts - offset
                    sample = samples_by_ts.get(ts)
                    if sample is None:
                        timeline.append(None)
                    else:
                        timeline.append(bool(sample['ok']))

                result[device] = {
                    "status": "up" if success_rate >= 50 else "down",
                    "success_rate": success_rate,
                    "total_samples": total,
                    "successful_samples": successful,
                    "avg_rtt_ms": avg_rtt,
                    "last_check_ts": samples[0]['ts_epoch'] if samples else None,
                    "timeline": timeline
                }
            else:
                result[device] = {
                    "status": "unknown",
                    "success_rate": 0,
                    "total_samples": 0,
                    "successful_samples": 0,
                    "avg_rtt_ms": None,
                    "last_check_ts": None,
                    "timeline": [None for _ in range(window_seconds)]
                }
        
        return JSONResponse({"ping_status": result})
    finally:
        db.close()


@app.get("/api/config")
async def get_config():
    """Get configuration for the web app."""
    try:
        config = load_config()
        interval_seconds = config.get_interval_seconds()
        ping_interval = config.get_ping_interval_seconds()
        ping_window = config.get_ping_window_seconds()
        websocket_enabled = config.get_websocket_enabled()
        
        # Calculate polling intervals
        run_poll_interval = max(1, math.floor(interval_seconds / 2))
        
        return JSONResponse({
            "run_poll_interval_seconds": run_poll_interval,
            "ping_poll_interval_seconds": ping_interval,
            "ping_window_seconds": ping_window,
            "websocket_enabled": websocket_enabled
        })
    except Exception:
        # Return defaults if config not available
        return JSONResponse({
            "run_poll_interval_seconds": 2,
            "ping_poll_interval_seconds": 1,
            "ping_window_seconds": 60,
            "websocket_enabled": False
        })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back for ping/pong or ignore other messages
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        await manager.disconnect(websocket)

