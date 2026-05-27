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
# Specification

Japanese: [specification.ja.md](specification.ja.md)

## System Components

- Collector: Executes SSH commands and ping probes on configured devices.
- Database: Stores command runs and ping samples in `data/current.sqlite3`.
- Web App: Exposes UI and API endpoints for viewing, diffing, and exporting data.

## Data Collection Behavior

- Global command interval: `interval_seconds`.
- Per-command override: `commands[].interval_seconds` (validated range: 5-60 seconds).
- Ping interval: `ping_interval_seconds`.
- Standalone ping targets: `ping_targets[]` (optional, max 3 entries).
- Command history retention: `history_size` latest runs per device/command.
- Filtering:
- `global_filters.line_exclude_substrings` removes matching lines.
- `global_filters.output_exclude_substrings` marks run as filtered (excluded from standard views).
- Output truncation: `max_output_lines` after filtering.

## Configuration Schema

Main required blocks in `config.yaml`:

- `commands[]`
- `devices[]`

Main optional blocks:

- `collector.max_workers`
- `ping_targets[].name`
- `ping_targets[].host`
- `websocket.enabled`
- `websocket.ping_interval`
- `ssh.persistent_connections`
- `ssh.connection_timeout`
- `ssh.max_reconnect_attempts`
- `ssh.reconnect_backoff_base`
- `ssh.initial_commands`
- `devices[].initial_commands`

`ssh.initial_commands` run once immediately after every SSH login for all devices.
`devices[].initial_commands` are appended for that device. With persistent SSH
connections they run once per connection, and after reconnects. Without persistent
connections they run at the start of each short-lived command session.

Reference example: [`config.example.yaml`](../config.example.yaml)

## Web API (Implemented)

- `GET /api/commands`
- `GET /api/devices`
- `GET /api/runs/{command}`
- `GET /api/runs/{command}/side_by_side`
- `GET /api/diff/history`
- `GET /api/diff/devices`
- `GET /api/ping`
- `GET /api/config`
- `GET /api/collector/status`
- `POST /api/collector/pause`
- `POST /api/collector/resume`
- `POST /api/collector/stop`
- `POST /api/collector/mode`
- `POST /api/collector/run_once`
- `GET /api/export/run`
- `GET /api/export/bulk`
- `GET /api/export/diff`
- `GET /api/export/ping`
- `GET /ws` (WebSocket endpoint)

## Notable Clarifications

- Scheduling is interval-based. Cron syntax is not used in the current implementation.
- WebSocket updates are optional (`websocket.enabled: true`) and fallback polling remains available.
