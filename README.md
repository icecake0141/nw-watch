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
# nw-watch - Network Device CLI Monitor
[![CI](https://github.com/icecake0141/nw-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/icecake0141/nw-watch/actions/workflows/ci.yml)

Japanese: [README.ja.md](README.ja.md)

nw-watch collects CLI outputs and ping health from network devices over SSH, stores data in SQLite, and serves real-time monitoring and diff views through a FastAPI web UI.

## Installation

### Option 1: Docker

```bash
git clone https://github.com/icecake0141/nw-watch.git
cd nw-watch
cp config.example.yaml config.yaml
cp .env.example .env
# edit config.yaml and .env
docker-compose up -d
```

Open `http://127.0.0.1:8000`.

### Option 2: Local

```bash
pip install -e ".[dev]"
cp config.example.yaml config.yaml
# set DEVICE*_PASSWORD environment variables
PYTHONPATH=src python -m nw_watch.collector.main --config config.yaml
PYTHONPATH=src uvicorn nw_watch.webapp.main:app --host 127.0.0.1 --port 8000
```

## Documentation

- [Documentation Index (English)](docs/README.md)
- [ドキュメント一覧 (日本語)](docs/README.ja.md)
- [Specification](docs/specification.md) | [仕様書](docs/specification.ja.md)
- [Testing](docs/testing.md) | [テスト](docs/testing.ja.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md) | [トラブルシューティング](docs/TROUBLESHOOTING.ja.md)
- [Collector Controls](docs/collector-controls.md) | [コレクター制御](docs/collector-controls.ja.md)
- [Web UI Screenshots](docs/webui-screenshots.md) | [Web UI スクリーンショット](docs/webui-screenshots.ja.md)
- [Improvement Suggestions](docs/IMPROVEMENT_SUGGESTIONS.md) | [改善提案](docs/IMPROVEMENT_SUGGESTIONS.ja.md)
