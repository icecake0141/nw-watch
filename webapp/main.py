"""Web application for network device monitoring."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import time
import math
from typing import List, Dict, Any, Optional
from shared.db import Database
from shared.diff import generate_diff, generate_side_by_side_diff

app = FastAPI(title="Network Watch")

# Setup templates and static files
templates = Jinja2Templates(directory="webapp/templates")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")


def get_db() -> Optional[Database]:
    """Get database connection."""
    db_path = Path('data/current.sqlite3')
    if not db_path.exists():
        return None
    return Database(str(db_path))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main page."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/commands")
async def get_commands():
    """Get list of all commands."""
    db = get_db()
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
    db = get_db()
    if not db:
        return JSONResponse({"devices": []})
    
    try:
        devices = db.get_all_devices()
        return JSONResponse({"devices": devices})
    finally:
        db.close()


@app.get("/api/runs/{command}")
async def get_runs(command: str, device: Optional[str] = None, limit: int = 10):
    """Get command runs for a specific command."""
    db = get_db()
    if not db:
        return JSONResponse({"runs": {}})
    
    try:
        devices = [device] if device else db.get_all_devices()
        result = {}
        
        for dev in devices:
            runs = db.get_latest_runs(dev, command, limit=limit)
            result[dev] = runs
        
        return JSONResponse({"runs": result})
    finally:
        db.close()


@app.get("/api/diff/history")
async def get_history_diff(command: str, device: str):
    """Get diff between latest and previous run."""
    db = get_db()
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)
    
    try:
        runs = db.get_latest_runs(device, command, limit=2)
        
        if len(runs) < 2:
            return JSONResponse({
                "diff": "Not enough history for comparison",
                "has_diff": False
            })
        
        latest = runs[0]
        previous = runs[1]
        
        diff = generate_diff(
            previous.get('output_text', ''),
            latest.get('output_text', '')
        )
        
        return JSONResponse({
            "diff": diff,
            "has_diff": len(diff) > 0,
            "latest_ts": latest['ts_epoch'],
            "previous_ts": previous['ts_epoch']
        })
    finally:
        db.close()


@app.get("/api/diff/devices")
async def get_device_diff(command: str, device_a: str, device_b: str):
    """Get diff between two devices for the same command."""
    db = get_db()
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)
    
    try:
        run_a = db.get_latest_run(device_a, command)
        run_b = db.get_latest_run(device_b, command)
        
        if not run_a or not run_b:
            return JSONResponse({
                "diff": "Data not available for both devices",
                "has_diff": False
            })
        
        diff = generate_side_by_side_diff(
            run_a.get('output_text', ''),
            run_b.get('output_text', ''),
            label_a=device_a,
            label_b=device_b
        )
        
        return JSONResponse({
            "diff": diff,
            "has_diff": len(diff) > 0,
            "device_a_ts": run_a['ts_epoch'],
            "device_b_ts": run_b['ts_epoch']
        })
    finally:
        db.close()


@app.get("/api/ping")
async def get_ping_status(window_seconds: int = 60):
    """Get ping status for all devices."""
    db = get_db()
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
                
                result[device] = {
                    "status": "up" if success_rate >= 50 else "down",
                    "success_rate": success_rate,
                    "total_samples": total,
                    "successful_samples": successful,
                    "avg_rtt_ms": avg_rtt,
                    "last_check_ts": samples[0]['ts_epoch'] if samples else None
                }
            else:
                result[device] = {
                    "status": "unknown",
                    "success_rate": 0,
                    "total_samples": 0,
                    "successful_samples": 0,
                    "avg_rtt_ms": None,
                    "last_check_ts": None
                }
        
        return JSONResponse({"ping_status": result})
    finally:
        db.close()


@app.get("/api/config")
async def get_config():
    """Get configuration for the web app."""
    # Load config to get intervals
    from shared.config import Config
    try:
        config = Config('config.yaml')
        interval_seconds = config.get_interval_seconds()
        ping_interval = config.get_ping_interval_seconds()
        ping_window = config.get_ping_window_seconds()
        
        # Calculate polling intervals
        run_poll_interval = max(1, math.floor(interval_seconds / 2))
        
        return JSONResponse({
            "run_poll_interval_seconds": run_poll_interval,
            "ping_poll_interval_seconds": ping_interval,
            "ping_window_seconds": ping_window
        })
    except Exception:
        # Return defaults if config not available
        return JSONResponse({
            "run_poll_interval_seconds": 2,
            "ping_poll_interval_seconds": 1,
            "ping_window_seconds": 60
        })
