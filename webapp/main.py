"""Web application for network device monitoring."""

import asyncio
import logging
import math
import re
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from yaml import YAMLError

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared.config import Config
from shared.db import Database
from shared.diff import generate_side_by_side_diff, generate_inline_char_diff
from shared.export import (
    export_run_as_text,
    export_run_as_json,
    export_bulk_runs_as_json,
    export_ping_data_as_csv,
    export_ping_data_as_json,
    export_diff_as_html,
    export_diff_as_text,
)
from webapp.websocket_manager import manager

logger = logging.getLogger(__name__)

# Background task state
_background_task = None
_last_db_mtime = None
_db_mtime_lock = asyncio.Lock()

# Constants for database monitoring
DATABASE_CHECK_INTERVAL_DIVISOR = 2  # Monitor at half the collection interval


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use in filenames.

    Removes or replaces characters that could be used for path traversal
    or other filename-based attacks. Allows only alphanumeric characters,
    underscores, hyphens, and periods.

    Args:
        name: The string to sanitize

    Returns:
        A sanitized version safe for use in filenames
    """
    # Replace any character that is not alphanumeric, underscore, hyphen, or period
    # with an underscore to prevent path traversal and other attacks
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


async def monitor_database_changes():
    """Background task to monitor database changes and notify WebSocket clients."""
    global _last_db_mtime

    # Check interval based on config
    try:
        config = load_config()
        check_interval = max(
            1,
            math.floor(config.get_interval_seconds() / DATABASE_CHECK_INTERVAL_DIVISOR),
        )
    except Exception:
        check_interval = 2

    logger.info("Starting database monitor task (interval: %ds)", check_interval)

    while True:
        try:
            if DATABASE_PATH.exists():
                current_mtime = DATABASE_PATH.stat().st_mtime

                async with _db_mtime_lock:
                    if _last_db_mtime is not None and current_mtime > _last_db_mtime:
                        # Database has been updated, notify WebSocket clients
                        await manager.broadcast_update("data_update")
                        logger.debug("Database updated, notified WebSocket clients")

                    _last_db_mtime = current_mtime

            await asyncio.sleep(check_interval)
        except Exception as exc:
            logger.error("Error in database monitor task: %s", exc)
            await asyncio.sleep(check_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global _background_task

    # Startup
    try:
        config = load_config()
        if config.get_websocket_enabled():
            _background_task = asyncio.create_task(monitor_database_changes())
            logger.info("WebSocket enabled, started database monitor task")
        else:
            logger.info("WebSocket disabled in configuration")
    except Exception as exc:
        logger.warning("Could not load config for WebSocket setup: %s", exc)

    yield

    # Shutdown
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass
        logger.info("Stopped database monitor task")


app = FastAPI(title="Network Watch", lifespan=lifespan)


# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Setup templates and static files
templates = Jinja2Templates(directory="webapp/templates")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

DEFAULT_HISTORY_SIZE = 10
DATABASE_PATH = Path("data/current.sqlite3")


@lru_cache(maxsize=1)
def load_config() -> Config:
    """Load config once (cached)."""
    return Config("config.yaml")


def resolve_history_size() -> int:
    """Return configured history size with safe fallback."""
    try:
        return load_config().get_history_size()
    except (FileNotFoundError, PermissionError, YAMLError) as exc:
        logger.warning("Config fallback for history size: %s", exc)
        return DEFAULT_HISTORY_SIZE


def get_db(history_size: int) -> Optional[Database]:
    """Get database connection."""
    if not DATABASE_PATH.exists():
        return None
    return Database(str(DATABASE_PATH), history_size=history_size)


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
            sorted_cmds = sorted(commands_cfg, key=lambda c: c.get("sort_order", 0))
            return JSONResponse(
                {"commands": [c.get("command_text") for c in sorted_cmds]}
            )
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
async def get_runs(
    command: str, device: Optional[str] = None, limit: Optional[int] = None
):
    """Get command runs for a specific command."""
    if limit is None:
        try:
            cfg = load_config()
            limit = cfg.get_history_size()
        except (FileNotFoundError, PermissionError, YAMLError) as exc:
            logger.warning("Config fallback for /api/runs: %s", exc)
            limit = DEFAULT_HISTORY_SIZE

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


@app.get("/api/runs/{command}/side_by_side")
async def get_runs_side_by_side(command: str):
    """Get command runs for all devices with character-level diff highlighting.

    Returns the latest run for each device with inline character-level diff
    highlighting to show differences between devices.
    """
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"devices": []})

    try:
        devices = db.get_all_devices()

        if len(devices) < 2:
            # Need at least 2 devices for comparison
            return JSONResponse(
                {
                    "devices": [],
                    "error": "Need at least 2 devices for side-by-side comparison",
                }
            )

        # Get latest run for each device
        device_runs = {}
        for device in devices:
            runs = db.get_latest_runs(device, command, limit=1, include_filtered=False)
            if runs:
                device_runs[device] = runs[0]

        if len(device_runs) < 2:
            return JSONResponse(
                {
                    "devices": [],
                    "error": "Need at least 2 devices with data for comparison",
                }
            )

        # For now, compare first two devices
        # In future, this could be extended to support N-way comparison
        device_list = sorted(device_runs.keys())
        device_a = device_list[0]
        device_b = device_list[1]

        run_a = device_runs[device_a]
        run_b = device_runs[device_b]

        text_a = run_a.get("output_text", "")
        text_b = run_b.get("output_text", "")

        # Generate character-level diff
        highlighted_a, highlighted_b = generate_inline_char_diff(text_a, text_b)

        # Build response
        result = {
            "devices": [
                {
                    "name": device_a,
                    "run": {
                        "ts_epoch": run_a["ts_epoch"],
                        "duration_ms": run_a["duration_ms"],
                        "ok": run_a["ok"],
                        "is_truncated": run_a.get("is_truncated", False),
                        "is_filtered": run_a.get("is_filtered", False),
                        "original_line_count": run_a.get("original_line_count"),
                        "output_text": text_a,
                        "output_html": highlighted_a,
                    },
                },
                {
                    "name": device_b,
                    "run": {
                        "ts_epoch": run_b["ts_epoch"],
                        "duration_ms": run_b["duration_ms"],
                        "ok": run_b["ok"],
                        "is_truncated": run_b.get("is_truncated", False),
                        "is_filtered": run_b.get("is_filtered", False),
                        "original_line_count": run_b.get("original_line_count"),
                        "output_text": text_b,
                        "output_html": highlighted_b,
                    },
                },
            ],
            "has_diff": text_a != text_b,
        }

        return JSONResponse(result)
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
            return JSONResponse(
                {
                    "diff": "Not enough history for comparison",
                    "has_diff": False,
                    "diff_format": "text",
                }
            )

        latest = runs[0]
        previous = runs[1]

        previous_text = previous.get("output_text", "")
        latest_text = latest.get("output_text", "")
        diff = generate_side_by_side_diff(
            previous_text, latest_text, label_a="Previous", label_b="Latest"
        )
        has_diff = previous_text != latest_text

        return JSONResponse(
            {
                "diff": diff,
                "diff_format": "html",
                "has_diff": has_diff,
                "latest_ts": latest["ts_epoch"],
                "previous_ts": previous["ts_epoch"],
            }
        )
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
            return JSONResponse(
                {
                    "diff": "Data not available for both devices",
                    "has_diff": False,
                    "diff_format": "text",
                }
            )

        run_a_text = run_a.get("output_text", "")
        run_b_text = run_b.get("output_text", "")
        diff = generate_side_by_side_diff(
            run_a_text, run_b_text, label_a=device_a, label_b=device_b
        )
        has_diff = run_a_text != run_b_text

        return JSONResponse(
            {
                "diff": diff,
                "diff_format": "html",
                "has_diff": has_diff,
                "device_a_ts": run_a["ts_epoch"],
                "device_b_ts": run_b["ts_epoch"],
            }
        )
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
            successful = sum(1 for s in samples if s["ok"])

            if total > 0:
                success_rate = (successful / total) * 100
                avg_rtt = None
                if successful > 0:
                    rtts = [
                        s["rtt_ms"]
                        for s in samples
                        if s["ok"] and s["rtt_ms"] is not None
                    ]
                    if rtts:
                        avg_rtt = sum(rtts) / len(rtts)
                # Build timeline (oldest -> newest)
                samples_by_ts = {s["ts_epoch"]: s for s in samples}
                timeline = []
                for offset in range(window_seconds - 1, -1, -1):
                    ts = current_ts - offset
                    sample = samples_by_ts.get(ts)
                    if sample is None:
                        timeline.append(None)
                    else:
                        timeline.append(bool(sample["ok"]))

                result[device] = {
                    "status": "up" if success_rate >= 50 else "down",
                    "success_rate": success_rate,
                    "total_samples": total,
                    "successful_samples": successful,
                    "avg_rtt_ms": avg_rtt,
                    "last_check_ts": samples[0]["ts_epoch"] if samples else None,
                    "timeline": timeline,
                }
            else:
                result[device] = {
                    "status": "unknown",
                    "success_rate": 0,
                    "total_samples": 0,
                    "successful_samples": 0,
                    "avg_rtt_ms": None,
                    "last_check_ts": None,
                    "timeline": [None for _ in range(window_seconds)],
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

        return JSONResponse(
            {
                "run_poll_interval_seconds": run_poll_interval,
                "ping_poll_interval_seconds": ping_interval,
                "ping_window_seconds": ping_window,
                "websocket_enabled": websocket_enabled,
            }
        )
    except Exception:
        # Return defaults if config not available
        return JSONResponse(
            {
                "run_poll_interval_seconds": 2,
                "ping_poll_interval_seconds": 1,
                "ping_window_seconds": 60,
                "websocket_enabled": False,
            }
        )


@app.get("/api/export/run")
async def export_run(command: str, device: str, format: str = "text"):
    """Export a single command run output.

    Args:
        command: Command text
        device: Device name
        format: Export format ('text' or 'json')
    """
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)

    try:
        run = db.get_latest_run(device, command, include_filtered=False)

        if not run:
            return JSONResponse({"error": "No data available"}, status_code=404)

        if format == "json":
            content = export_run_as_json(run, device, command)
            filename = f"{sanitize_filename(device)}_{sanitize_filename(command.replace(' ', '_'))}_{run['ts_epoch']}.json"
            return Response(
                content=content,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:  # text format
            content = export_run_as_text(run, device, command)
            filename = f"{sanitize_filename(device)}_{sanitize_filename(command.replace(' ', '_'))}_{run['ts_epoch']}.txt"
            return PlainTextResponse(
                content=content,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
    finally:
        db.close()


@app.get("/api/export/bulk")
async def export_bulk(command: str, format: str = "json"):
    """Export all device outputs for a command.

    Args:
        command: Command text
        format: Export format (only 'json' supported currently)
    """
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)

    try:
        devices = db.get_all_devices()
        runs_by_device = {}

        for device in devices:
            runs = db.get_latest_runs(device, command, limit=1, include_filtered=False)
            if runs:
                runs_by_device[device] = runs

        if not runs_by_device:
            return JSONResponse({"error": "No data available"}, status_code=404)

        content = export_bulk_runs_as_json(runs_by_device, command)
        filename = f"bulk_{sanitize_filename(command.replace(' ', '_'))}_{int(time.time())}.json"

        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        db.close()


@app.get("/api/export/diff")
async def export_diff(
    command: str,
    device: Optional[str] = None,
    device_a: Optional[str] = None,
    device_b: Optional[str] = None,
    format: str = "html",
):
    """Export diff view.

    Args:
        command: Command text
        device: Device name for history diff
        device_a: First device for device comparison
        device_b: Second device for device comparison
        format: Export format ('html' or 'text')
    """
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)

    try:
        # Determine diff type
        if device and not device_a and not device_b:
            # History diff
            runs = db.get_latest_runs(device, command, limit=2, include_filtered=False)

            if len(runs) < 2:
                return JSONResponse(
                    {"error": "Not enough history for comparison"}, status_code=404
                )

            latest = runs[0]
            previous = runs[1]

            previous_text = previous.get("output_text", "")
            latest_text = latest.get("output_text", "")
            diff_html = generate_side_by_side_diff(
                previous_text, latest_text, label_a="Previous", label_b="Latest"
            )
            label_a = "Previous"
            label_b = "Latest"
            filename_prefix = f"history_diff_{sanitize_filename(device)}_{sanitize_filename(command.replace(' ', '_'))}"

        elif device_a and device_b:
            # Device diff
            run_a = db.get_latest_run(device_a, command, include_filtered=False)
            run_b = db.get_latest_run(device_b, command, include_filtered=False)

            if not run_a or not run_b:
                return JSONResponse(
                    {"error": "Data not available for both devices"}, status_code=404
                )

            run_a_text = run_a.get("output_text", "")
            run_b_text = run_b.get("output_text", "")
            diff_html = generate_side_by_side_diff(
                run_a_text, run_b_text, label_a=device_a, label_b=device_b
            )
            label_a = device_a
            label_b = device_b
            filename_prefix = f"device_diff_{sanitize_filename(device_a)}_vs_{sanitize_filename(device_b)}_{sanitize_filename(command.replace(' ', '_'))}"
        else:
            return JSONResponse({"error": "Invalid parameters"}, status_code=400)

        if format == "html":
            content = export_diff_as_html(diff_html, label_a, label_b)
            filename = f"{filename_prefix}_{int(time.time())}.html"
            return Response(
                content=content,
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:  # text format
            content = export_diff_as_text(diff_html, label_a, label_b)
            filename = f"{filename_prefix}_{int(time.time())}.txt"
            return PlainTextResponse(
                content=content,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
    finally:
        db.close()


@app.get("/api/export/ping")
async def export_ping(device: str, format: str = "csv", window_seconds: int = 3600):
    """Export ping data for a device.

    Args:
        device: Device name
        format: Export format ('csv' or 'json')
        window_seconds: Time window in seconds (default: 1 hour)
    """
    db = get_db(resolve_history_size())
    if not db:
        return JSONResponse({"error": "Database not available"}, status_code=503)

    try:
        current_ts = int(time.time())
        since_ts = current_ts - window_seconds

        samples = db.get_ping_samples(device, since_ts)

        if not samples:
            return JSONResponse({"error": "No ping data available"}, status_code=404)

        if format == "json":
            content = export_ping_data_as_json(samples, device)
            filename = f"ping_{sanitize_filename(device)}_{int(time.time())}.json"
            return Response(
                content=content,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:  # csv format
            content = export_ping_data_as_csv(samples, device)
            filename = f"ping_{sanitize_filename(device)}_{int(time.time())}.csv"
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
    finally:
        db.close()


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
            else:
                logger.debug("Received unexpected WebSocket message: %s", data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        await manager.disconnect(websocket)
