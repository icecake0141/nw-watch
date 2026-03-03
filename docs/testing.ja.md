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
# テスト

English: [testing.md](testing.md)

## テスト対象

本リポジトリでは、主に以下をテストしています。

- 設定バリデーションとデフォルト値
- Collector の挙動（コマンド実行、ping、スケジューリング、制御状態）
- データベース保存と履歴保持
- Web API エンドポイントとエクスポート機能
- WebSocket 動作
- セキュリティ関連（入力検証、セキュリティヘッダー）

テスト配置: [`tests/`](../tests)

## ローカル検証コマンド

依存関係インストール:

```bash
pip install -e ".[dev]"
```

フォーマット確認:

```bash
black --check --diff .
```

Lint:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=.git,__pycache__,data,tests
```

型チェック:

```bash
mypy --install-types --non-interactive --ignore-missing-imports src/nw_watch
```

テスト:

```bash
pytest -v --tb=short --cov=nw_watch --cov-report=xml --cov-report=term
```

## CI 参照

CI 設定ファイル: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

PR では Python 3.12、`main` / `develop` への push では Python 3.11/3.12 で lint とテストが実行されます。
