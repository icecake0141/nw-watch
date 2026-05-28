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
# トラブルシューティング

English: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 接続トラブル

### SSH で接続できない

- `ping <device_ip>` と `nc -zv <device_ip> 22` で到達性を確認
- `password_env_key` と環境変数名の一致を確認
- `device_type` が Netmiko 対応名と一致するか確認
- `ssh.connection_timeout` / `ssh.max_reconnect_attempts` を調整

### 接続が不安定

- `interval_seconds` が長すぎないか確認
- 監視対象機器の CPU/メモリ負荷を確認
- `ssh.reconnect_backoff_base` を調整

## 権限エラー

### `config.yaml` が読めない

```bash
chmod 600 config.yaml
chown <user>:<group> config.yaml
```

### SQLite に書き込めない

```bash
chmod 755 data/
chown <user>:<group> data/
```

Docker 利用時はホスト側 `data/` の所有者も確認してください。

## データベース問題

### `database is locked`

- 同じ `data/` を複数 collector が共有していないか確認
- ディスク空き容量を確認 (`df -h data/`)
- 必要に応じてサービス停止後に `*.sqlite3-wal` / `*.sqlite3-shm` を整理

### データが表示されない

- collector が起動しているか確認
- `data/current.sqlite3` が更新されているか確認
- Web UI の `/api/config` でポーリング/WS設定を確認

## Web UI 問題

### WebSocket が接続できない

- `config.yaml` の `websocket.enabled` を確認
- ブラウザ開発者ツールの Network/Console を確認
- 未有効時はポーリング動作が正常なので API 応答を優先確認

## Docker 問題

### コンテナが Restart を繰り返す

- `docker-compose logs nw-watch` で `runtime_startup_failed`、`Config file not found`、`Configuration validation failed` を確認
- `config.yaml` がファイルとして存在するか確認（存在しない場合は `cp config.example.yaml config.yaml`）
- `.env` の `DEVICE*_PASSWORD` が空ではないか確認
- `docker-compose build --no-cache` で Python 3.12 ベースのイメージを再ビルド
- runtime wrapper は collector または Uvicorn のどちらかが終了した場合、残りのプロセスも停止して終了コードをログに出します

## ログの見方

collector のログには `category=` が出力されます。主な分類:

- `ssh_timeout`: SSH 接続タイムアウト
- `network_unreachable` / `host_unreachable`: 経路またはホスト到達不可
- `ssh_connection_refused`: TCP 接続拒否
- `ssh_authentication_failed`: 認証失敗
- `ssh_disconnected`: セッション切断
- `ping_failed` / `ping_exception`: ping 失敗または ping コマンド実行失敗
- `invalid_ping_host`: `ping_host` の形式不正

## 追加調査時に確認する情報

- collector / webapp のログ
- `config.yaml`（パスワードは伏せる）
- `docker-compose ps` と `docker-compose logs -f`
- 発生時刻（JST）と再現手順
