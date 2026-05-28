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
# 仕様書

English: [specification.md](specification.md)

## システム構成

- Collector: 設定済みデバイスに対して SSH コマンド実行と ping 監視を行う。
- Database: コマンド実行結果と ping サンプルを `data/current.sqlite3` に保存する。
- Web App: データ表示、差分比較、エクスポート API を提供する。
- Runtime Wrapper: Collector と Web App を一括起動し、終了シグナル時に両方を停止する。

## データ収集仕様

- グローバル実行間隔: `interval_seconds`
- コマンド個別上書き: `commands[].interval_seconds`（許容範囲 5-60 秒）
- ping 間隔: `ping_interval_seconds`
- 履歴保持: `history_size`（デバイス/コマンドごとに最新 N 件）
- フィルター:
- `global_filters.line_exclude_substrings` は一致行を削除
- `global_filters.output_exclude_substrings` は run を filtered 扱いにする
- 出力上限: `max_output_lines`（フィルター後）

## 設定スキーマ

`config.yaml` の主な必須ブロック:

- `commands[]`
- `devices[]`

主な任意ブロック:

- `collector.max_workers`
- `websocket.enabled`
- `websocket.ping_interval`
- `ssh.persistent_connections`
- `ssh.connection_timeout`
- `ssh.max_reconnect_attempts`
- `ssh.reconnect_backoff_base`
- `ssh.initial_commands`
- `devices[].initial_commands`

`ssh.initial_commands` は全デバイスで SSH ログイン直後に一度実行されます。
`devices[].initial_commands` は対象デバイスで追加実行されます。永続 SSH 接続では
接続ごと、および再接続後に一度実行されます。永続接続を無効にした場合は、
各コマンド用の短期セッション開始時に実行されます。

設定例: [`config.example.yaml`](../config.example.yaml)

## Web API（実装済み）

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
- `GET /ws`（WebSocket エンドポイント）

## 起動方式

- 一括起動: `python -m nw_watch.runtime --config config.yaml --host 127.0.0.1 --port 8000`
- Docker: `docker-compose up -d` は runtime wrapper を使って collector と Uvicorn を同一コンテナ内で管理する。
- `NW_WATCH_CONFIG` と `NW_WATCH_DATA_DIR` 環境変数で Web App の設定ファイルとデータディレクトリを指定できる。

## 補足（不整合解消）

- スケジューリングは interval ベースであり、現行実装に cron 構文はありません。
- WebSocket は `websocket.enabled: true` の場合のみ有効で、未有効時はポーリングで動作します。
