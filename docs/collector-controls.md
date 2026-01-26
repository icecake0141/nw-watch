<!--
Copyright 2026 icecake0141
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->
# Collector Control Buttons - User Guide

## Overview

The Network Watch WEBGUI provides three control buttons to manage the collector process:
- **Pause Commands**: Temporarily suspend command execution
- **Resume Commands**: Resume command execution after pausing
- **Stop Collector**: Gracefully terminate the collector process

## How It Works

### Architecture

The control system uses a **file-based state mechanism** to communicate between the webapp and collector:

```
┌─────────────┐                ┌──────────────────┐                ┌───────────┐
│  WEBGUI     │                │  Control State   │                │ Collector │
│             │                │      File        │                │  Process  │
│  [Button]   │───(1) Click───>│                  │<──(2) Poll────│           │
│             │                │  JSON file with  │                │  Checks   │
│             │<──(3) Update───│  pause/stop      │                │  every    │
│  [Status]   │                │  flags           │                │  ~2 sec   │
└─────────────┘                └──────────────────┘                └───────────┘
```

1. **Button Click**: User clicks Pause/Resume/Stop button in WEBGUI
2. **API Call**: JavaScript calls REST API endpoint (`/api/collector/pause`, etc.)
3. **State Update**: API updates control state file (`control/collector_control.json`)
4. **UI Update**: Button and status text update immediately in the browser
5. **Collector Poll**: Collector reads control state file every ~2 seconds
6. **Action**: Collector pauses, resumes, or stops based on the state

### Control State File

Location: `control/collector_control.json` (or `$NW_WATCH_CONTROL_DIR/collector_control.json`)

Format:
```json
{
  "commands_paused": false,
  "shutdown_requested": false,
  "updated_at": 1769421307
}
```

## Button Behavior

### Pause Commands Button

**Initial State**: "⏸ Pause Commands" (enabled)

**When Clicked**:
1. Sends POST request to `/api/collector/pause`
2. Sets `commands_paused: true` in control state
3. Button changes to "▶ Resume Commands"
4. Status changes to "Collector: Paused"
5. Collector stops executing commands (but continues ping monitoring)

**Effect on Collector**:
- Command execution is skipped
- Ping monitoring continues
- Collector polls control state every 2 seconds
- No new command outputs are stored in database

### Resume Commands Button

**Initial State**: "▶ Resume Commands" (enabled, only visible when paused)

**When Clicked**:
1. Sends POST request to `/api/collector/resume`
2. Sets `commands_paused: false` in control state
3. Button changes back to "⏸ Pause Commands"
4. Status changes to "Collector: Running"
5. Collector resumes executing commands

### Stop Collector Button

**Initial State**: "⏹ Stop Collector" (enabled, red)

**When Clicked**:
1. Shows confirmation dialog: "Stop the collector process? Command execution will end."
2. If confirmed, sends POST request to `/api/collector/stop`
3. Sets both `commands_paused: true` and `shutdown_requested: true`
4. Button changes to "⏹ Collector Stopped" (disabled)
5. Pause button also becomes disabled
6. Status changes to "Collector: Stopped"
7. Collector gracefully shuts down on next poll cycle

**Effect on Collector**:
- Collector exits main loop
- Closes all SSH connections
- Closes database
- Process terminates

## Important Notes

### ⏱️ Timing Considerations

**There is a ~2 second delay** between clicking a button and the collector responding because:
- The collector polls the control state file every `control_poll_interval` (default: 2 seconds)
- The webapp updates the state file immediately, but the collector must read it on its next poll cycle
- This is **by design** to avoid excessive file I/O

**What you'll see**:
- ✅ WEBGUI updates **immediately** (< 100ms)
- ⏳ Collector responds **within 2 seconds**

### 🔄 Polling vs Real-Time

The control system is **polling-based**, not event-driven:
- Webapp writes to file
- Collector reads from file periodically
- No direct inter-process communication (IPC) like signals or sockets

This design choice provides:
- ✅ Simplicity
- ✅ Cross-platform compatibility
- ✅ No race conditions
- ✅ Atomic file operations
- ⚠️ Small delay in response

### 🔒 Thread Safety

- Control state file uses atomic writes (write to temp file, then rename)
- Collector uses proper locking for persistent SSH connections
- Safe to click buttons multiple times
- Safe to run multiple webapp instances (all read/write same file)

### 📝 Logging

Check logs to confirm collector is responding to button clicks:

```bash
# Collector logs when state changes
tail -f /path/to/collector.log

# Look for these messages:
# "Command execution paused via control state."
# "Command execution resumed via control state."
# "Shutdown requested via control state."
```

## API Endpoints

### GET /api/collector/status

Returns current collector state:

```json
{
  "commands_paused": false,
  "shutdown_requested": false,
  "status": "running",
  "updated_at": 1769421307
}
```

Status values:
- `"running"`: Commands executing normally
- `"paused"`: Commands paused, ping continues
- `"stopped"`: Shutdown requested, collector will terminate

### POST /api/collector/pause

Pauses command execution.

**Response** (200 OK):
```json
{
  "commands_paused": true,
  "shutdown_requested": false,
  "status": "paused",
  "updated_at": 1769421307
}
```

**Error** (409 Conflict):
```json
{
  "error": "Collector shutdown already requested."
}
```

### POST /api/collector/resume

Resumes command execution.

**Response** (200 OK):
```json
{
  "commands_paused": false,
  "shutdown_requested": false,
  "status": "running",
  "updated_at": 1769421307
}
```

### POST /api/collector/stop

Requests collector shutdown.

**Response** (200 OK):
```json
{
  "commands_paused": true,
  "shutdown_requested": true,
  "status": "stopped",
  "updated_at": 1769421307
}
```

## Troubleshooting

### Button click has no effect

**Symptom**: Button appears to do nothing when clicked

**Check**:
1. Open browser console (F12) for JavaScript errors
2. Check Network tab to see if API request was sent
3. Verify control state file exists and is writable: `ls -la control/`
4. Check webapp logs for errors

**Common causes**:
- JavaScript not loaded (check browser console)
- API endpoint not responding (check webapp server status)
- File permission issues on control directory
- Browser caching old JavaScript (hard refresh: Ctrl+Shift+R)

### Collector not responding to button clicks

**Symptom**: WEBGUI shows state change, but collector keeps running

**Check**:
1. Verify collector is actually running: `ps aux | grep collector`
2. Check if collector is reading the correct control file:
   ```bash
   # Default location
   cat control/collector_control.json
   
   # Or custom location if NW_WATCH_CONTROL_DIR is set
   echo $NW_WATCH_CONTROL_DIR
   ```
3. Check collector logs for control state messages
4. Verify file timestamps: `ls -l control/collector_control.json`
5. Wait at least 2-3 seconds after clicking button

**Common causes**:
- Collector using different control directory (environment variable mismatch)
- Collector not polling (check logs for errors)
- File permission issues preventing collector from reading file

### Pause/Resume cycle feels slow

**This is expected behavior**:
- WEBGUI updates instantly
- Collector responds within 2 seconds
- If this is too slow, you can modify `control_poll_interval` in collector code (not recommended)

## Testing

Run the integration tests to verify button functionality:

```bash
# Test webapp API endpoints
pytest tests/test_webapp.py::test_collector_pause_resume -v
pytest tests/test_webapp.py::test_collector_stop -v

# Test control state integration
pytest tests/test_collector_control_integration.py -v
```

All tests should PASS, confirming:
- ✅ Buttons call correct API endpoints
- ✅ API endpoints update control state file
- ✅ Control state persists correctly
- ✅ Collector logic reads and respects control state

## Manual Testing

### Test with Browser Automation

1. Start webapp:
   ```bash
   uvicorn nw_watch.webapp.main:app --host 127.0.0.1 --port 8000
   ```

2. Open browser to `http://127.0.0.1:8000`

3. Test pause:
   - Click "⏸ Pause Commands"
   - Verify status changes to "Collector: Paused"
   - Verify button changes to "▶ Resume Commands"
   - Check `control/collector_control.json`: `commands_paused` should be `true`

4. Test resume:
   - Click "▶ Resume Commands"
   - Verify status changes to "Collector: Running"
   - Verify button changes to "⏸ Pause Commands"
   - Check control file: `commands_paused` should be `false`

5. Test stop:
   - Click "⏹ Stop Collector"
   - Confirm dialog
   - Verify status changes to "Collector: Stopped"
   - Verify both buttons are disabled
   - Check control file: `shutdown_requested` should be `true`

### Test with Actual Collector

1. Start collector:
   ```bash
   python -m nw_watch.collector.main --config config.yaml
   ```

2. In another terminal, start webapp:
   ```bash
   uvicorn nw_watch.webapp.main:app --host 127.0.0.1 --port 8000
   ```

3. Open browser and click Pause button

4. Check collector logs - within 2 seconds you should see:
   ```
   Command execution paused via control state.
   ```

5. Click Resume button

6. Check collector logs - within 2 seconds you should see:
   ```
   Command execution resumed via control state.
   ```

7. Click Stop button and confirm

8. Check collector logs - within 2 seconds you should see:
   ```
   Shutdown requested via control state.
   Collector stopped by signal
   ```
   And the collector process should terminate.

## Summary

✅ **The Stop/Pause buttons ARE working correctly** in the current codebase.

The system uses a robust file-based control mechanism that:
- Updates instantly in the WEBGUI
- Propagates to the collector within ~2 seconds via polling
- Provides thread-safe, atomic state updates
- Works across all platforms

If you experience issues:
1. Check browser console for JavaScript errors
2. Verify control state file permissions
3. Check collector logs for error messages
4. Allow 2-3 seconds for collector to respond
5. Run integration tests to verify system health
