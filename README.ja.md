# nw-watch - ネットワークデバイス CLI モニター

Python製のネットワーク監視システムです。複数のネットワーク機器へSSHで接続し、コマンド出力とpingデータを収集し、包括的な差分表示に対応したリアルタイムWebインターフェースで確認できます。

> English: [README.md](README.md) | Web UI スクリーンショット: [docs/webui-screenshots.ja.md](docs/webui-screenshots.ja.md)

## 特徴

### データ収集
- **複数デバイスのSSH収集**: Netmikoを使用して複数のネットワーク機器へ同時にSSH接続
- **並列実行**: ThreadPoolExecutorを使用してデバイス間でコマンドを並列実行
- **継続的なping監視**: 設定可能なping間隔（デフォルト: 1秒）でデバイスの到達性を追跡
- **コマンド履歴**: 設定可能な実行履歴の保持（デフォルト: デバイス/コマンドごとに10件）
- **堅牢なエラー処理**: 接続失敗やコマンドエラーを詳細なログと共に適切に処理

### 出力処理
- **スマートな行フィルタリング**: コマンド出力から特定の文字列を含む行を削除
  - グローバルフィルターは全コマンドに適用
  - コマンド単位のフィルターオーバーライドで細かい制御が可能
- **出力除外パターン**: エラーパターン（"% Invalid"、"% Ambiguous"など）を含む出力を自動的にマークして非表示
- **出力トリミング**: 設定可能な行数で出力の長さを制限してデータベースの肥大化を防止
- **メタデータ追跡**: 各実行の元の行数、トリミング状態、フィルター状態を記録

### Webインターフェース
- **リアルタイム更新**: FastAPI製のWebアプリケーションで設定可能な自動更新間隔
- **デバイス接続ダッシュボード**: 60秒の接続履歴を表示するビジュアルなpingタイムライン
  - カラーコード付きタイル（緑: 成功、赤: 失敗、灰: データなし）
  - 成功率とサンプル数
  - 平均RTT（往復時間）表示
  - 最終チェックのタイムスタンプ
- **コマンドタブ**: コマンドごとにグループ化された出力のビュー
  - 設定による並べ替え可能なタブ
  - デバイス別の出力履歴（新しい順）
  - タイムスタンプ、実行時間、ステータスを表示する展開可能な実行エントリ
  - 成功/エラー、フィルター済み、トリミング済みの状態を示すビジュアルバッジ
- **包括的な差分ビュー**:
  - **履歴差分**: 同一デバイスの前回 vs 最新の出力を比較
  - **デバイス間差分**: 同一コマンドの異なるデバイス間の出力を比較
  - カラーコード付きの変更を含むHTMLベースの並列比較
- **自動更新制御**: 手動更新オプション付きで自動更新の一時停止/再開が可能
- **JSTタイムゾーン表示**: すべてのタイムスタンプを日本標準時（UTC+9）で表示

## クイックスタート

### 1. 依存関係をインストール

```bash
pip install -e ".[dev]"
```

### 2. デバイス設定

例の設定ファイルをコピーし、デバイス情報を編集します:

```bash
cp config.example.yaml config.yaml
```

`config.yaml` を編集し（パスワードは環境変数で指定）、監視対象の機器を追加します:

```bash
export DEVICEA_PASSWORD="password123"
export DEVICEB_PASSWORD="password123"
```

```yaml
interval_seconds: 5
ping_interval_seconds: 1
ping_window_seconds: 60
history_size: 10
max_output_lines: 500

global_filters:
  line_exclude_substrings:
    - "Temperature"
  output_exclude_substrings:
    - "% Invalid"

commands:
  - name: "show_version"
    command_text: "show version"
    filters:
      line_exclude_substrings:
        - "uptime"
  - name: "interfaces_status"
    command_text: "show interfaces status"
  - name: "ip_int_brief"
    command_text: "show ip interface brief"

devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password_env_key: "DEVICEA_PASSWORD"
    device_type: "cisco_ios"  # netmiko のデバイスタイプ
    ping_host: "192.168.1.1"

  - name: "DeviceB"
    host: "192.168.1.2"
    port: 22
    username: "admin"
    password_env_key: "DEVICEB_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "192.168.1.2"
```

### 3. コレクターを起動

コレクターがデバイスへ接続してデータを収集します:

```bash
python -m collector.main --config config.yaml
```

コレクターの動作:
- 設定されたコマンドを5秒（設定可能）間隔で実行
- 各デバイスに1秒間隔でping
- SQLiteデータベース（`data/current.sqlite3`）に保存
- デバイス／コマンドごとに最新10件を保持

### 4. Webアプリを起動

別ターミナルでWebサーバーを起動します:

```bash
uvicorn webapp.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Web UIへアクセス

ブラウザで以下にアクセスします:

```
http://127.0.0.1:8000
```

## プロジェクト構成

```
nw-watch/
├── collector/          # データ収集モジュール
│   ├── __init__.py
│   └── main.py        # コレクターのメインロジック
├── webapp/            # Webアプリケーションモジュール
│   ├── __init__.py
│   ├── main.py        # FastAPIアプリ
│   ├── templates/     # Jinja2テンプレート
│   │   └── index.html
│   └── static/        # 静的ファイル
│       ├── style.css
│       └── app.js
├── shared/            # 共有ユーティリティ
│   ├── __init__.py
│   ├── config.py      # 設定ローダー
│   ├── db.py          # DB操作
│   ├── diff.py        # 差分生成
│   └── filters.py     # 出力フィルタリング・トリミング
├── tests/             # テストスイート
│   ├── __init__.py
│   ├── test_diff.py
│   ├── test_filters.py
│   ├── test_truncate.py
│   ├── test_db.py
│   └── test_webapp.py
├── data/              # DB保存先（実行時に生成）
│   └── .gitkeep
├── config.example.yaml
├── pyproject.toml
└── README.md
```

## 設定

### 基本設定

- `interval_seconds`: コマンド実行間隔（秒）
- `ping_interval_seconds`: ping実行間隔（秒）
- `ping_window_seconds`: pingタイムラインのウィンドウ秒数
- `history_size`: デバイス／コマンドごとに保持する履歴件数
- `max_output_lines`: フィルタ後に保持する最大行数（超過分はトリミング）

### デバイス

- `name`, `host`, `port`, `device_type`, `ping_host`
- `username`
- `password_env_key`: **SSHパスワードを格納する環境変数名**

### コマンド

コマンドは一度定義すると各デバイスで実行されます。任意でフィルターと`sort_order`（タブ順）を設定できます。

- `command_text`: CLIコマンド
- `filters.line_exclude_substrings`: グローバルな行フィルターを上書き
- `filters.output_exclude_substrings`: マッチした場合に出力を「フィルタ済み／非表示」として扱う

### フィルター

- `global_filters.line_exclude_substrings`: マッチする行を出力から除外
- `global_filters.output_exclude_substrings`: マッチした場合に「フィルタ済み」としてマーク（UIで非表示）
- コマンド単位のフィルターがグローバル設定を上書きします。

## データベーススキーマ

効率的なクエリとアトミックな更新のために設計された以下のSQLiteスキーマを使用します:

### テーブル

**devices**
- `id`: 主キー（自動インクリメント）
- `name`: 一意のデバイス名

**commands**
- `id`: 主キー（自動インクリメント）
- `command_text`: 一意のコマンドテキスト

**runs** - コマンド実行履歴
- `id`: 主キー（自動インクリメント）
- `device_id`: devicesテーブルへの外部キー
- `command_id`: commandsテーブルへの外部キー
- `ts_epoch`: UTCエポック秒でのタイムスタンプ
- `output_text`: 処理済みのコマンド出力（フィルタリング/トリミング後）
- `ok`: 成功フラグ（成功時1、失敗時0）
- `error_message`: 失敗時のエラー詳細
- `duration_ms`: 実行時間（ミリ秒）
- `is_filtered`: 出力が除外パターンに一致したことを示すフラグ
- `is_truncated`: 出力がトリミングされたことを示すフラグ
- `original_line_count`: フィルタリング/トリミング前の行数

**ping_samples** - ping監視データ
- `id`: 主キー（自動インクリメント）
- `device_id`: devicesテーブルへの外部キー
- `ts_epoch`: UTCエポック秒でのタイムスタンプ
- `ok`: 成功フラグ（成功時1、失敗時0）
- `rtt_ms`: ラウンドトリップ時間（ミリ秒、失敗時はnull）
- `error_message`: 失敗時のエラー詳細

### インデックス
- `idx_runs_device_command`: 高速な実行クエリのための(device_id, command_id)の複合インデックス
- `idx_runs_ts`: 時間ベースのクエリのためのts_epochのインデックス
- `idx_ping_device_ts`: pingタイムラインクエリのための(device_id, ts_epoch)の複合インデックス

## Web UI機能

### デバイス接続パネル
- 60秒のリアルタイムpingタイムライン（左が過去、右が最新）
- 成功率とサンプル数
- 平均RTT

### コマンドタブ
- コマンドごとに1タブ
- デバイス別の出力履歴（新しい順）
- メタデータ付きの展開表示

### 差分ビュー
- **前回 vs 最新**: 同一デバイスの連続実行結果を比較
- **デバイスA vs デバイスB**: デバイス間で出力を比較
- 行レベル差分を色付け表示（緑／赤）

### 自動更新制御
- 自動更新の一時停止／再開ボタン（停止中は画面にバナー表示）
- 一時停止中も手動更新ボタンで即時リロード可能
- ポーリング間隔は `interval_seconds` と `ping_interval_seconds` から算出

## テスト実行

```bash
# 開発依存を含めてインストール
pip install -e ".[dev]"

# すべてのテストを実行
pytest

# 特定ファイルのテストを実行
pytest tests/test_diff.py

# 詳細表示
pytest -v

# カバレッジ付き
pytest --cov=shared --cov=collector --cov=webapp
```

## 開発

### 新しいデバイスタイプの追加

[Netmiko](https://github.com/ktbyers/netmiko) が対応するデバイスタイプなら利用できます。代表的なタイプ:

- `cisco_ios`
- `cisco_nxos`
- `juniper_junos`
- `arista_eos`
- `hp_procurve`

### フィルターの拡張

カスタムのフィルタリングロジックを追加するには:

1. `shared/filters.py` を編集
2. フィルター関数を追加
3. `process_output()` に新しいフィルターを組み込む
4. `tests/test_filters.py` にテストを追加

### UIのカスタマイズ

- テンプレート: `webapp/templates/index.html`
- スタイル: `webapp/static/style.css`
- JavaScript: `webapp/static/app.js`

## アーキテクチャ

### データフロー

1. **Collector** がNetmikoを使用してSSH経由でデバイスに接続
2. ThreadPoolExecutorを使用してコマンドを並列実行（設定可能な最大ワーカー数: 20）
3. 生の出力をフィルタリングとトリミングのパイプライン経由で処理
4. 結果をセッション専用のSQLiteデータベース（`session_{epoch}.sqlite3`）に保存
5. 各収集サイクル後にセッションデータベースを`current.sqlite3`にアトミックにコピー
6. **Web App** が`current.sqlite3`から読み取り（読み取り専用）、FastAPI REST API経由でデータを提供
7. **フロントエンド** が設定された間隔でAPIエンドポイントをポーリングし、UIを動的に更新

### データベースライフサイクルとアトミック更新

システムはアトミックなデータベース操作によってデータの一貫性を保証します:

1. 新しいコレクターセッションが`data/session_{epoch}.sqlite3`を作成
2. すべての収集更新がセッションデータベースに保存される
3. 各収集サイクル後:
   - 一時コピーを作成: `current.sqlite3.tmp`
   - 古い`current.sqlite3`を削除（存在する場合）
   - `current.sqlite3.tmp`を`current.sqlite3`にアトミックにリネーム
4. Webアプリは常に安定した`current.sqlite3`から読み取り
5. リーダーが不完全または不整合なデータを見ることがないことを保証

### ポーリング戦略

フロントエンドのポーリング間隔は設定から自動的に計算されます:
- **実行結果更新**: `max(1, floor(interval_seconds / 2))` 秒
- **ping更新**: `ping_interval_seconds` 秒
- 自動更新トグルを尊重（ユーザーが一時停止/再開可能）

### セキュリティ対策

- **入力検証**: pingホストをregexで検証してコマンドインジェクションを防止
- **環境変数**: パスワードを環境変数に保存（設定ファイルではなく）
- **SSH接続**: Netmikoの安全なSSH接続処理を使用
- **ファイルパーミッション**: 設定ファイルへの制限的なパーミッションを推奨（chmod 600）

## 動作要件

- Python 3.11+
- SSHでアクセス可能なネットワーク機器
- コマンドラインインターフェースを備えた機器

## セキュリティ考慮事項

**重要**: このシステムはネットワークデバイスの認証情報を扱うため、適切なセキュリティ対策を講じて展開する必要があります:

### 認証情報管理
- **環境変数**: 設定で`password_env_key`を使用して環境変数を参照（推奨アプローチ）
- **平文を避ける**: `config.yaml`に直接パスワードを保存しない（レガシーフォールバックは存在するが警告をログ出力）
- **シークレットマネージャー**: 本番環境では、シークレット管理システム（HashiCorp Vault、AWS Secrets Managerなど）との統合を検討

### ファイルパーミッション
- 設定ファイルのアクセスを制限: `chmod 600 config.yaml`
- データベースディレクトリに適切なパーミッションを設定
- 信頼できるユーザーのみにアプリケーションへのアクセスを制限

### ネットワークセキュリティ
- デバイスでサポートされている場合はSSH鍵ベース認証を使用
- Webインターフェースを認証付きリバースプロキシの背後に配置
- 本番環境ではWebインターフェースにHTTPSの使用を検討
- 監視対象デバイスのSSHポートへのネットワークアクセスを制限

### 入力検証
- コマンドインジェクションを防ぐためpingホストをregexパターンで検証
- 不正な形式のデータを防ぐため読み込み時に設定を検証

### ベストプラクティス
- 最小限の必要な権限でコレクターとWebアプリを実行
- SSH接続用に専用のサービスアカウントを使用
- 管理インターフェース用のネットワークセグメンテーションを実装
- セキュリティパッチのため依存関係を定期的に更新
- 不審なアクティビティについてログを監視

## ライセンス

MIT License

## トラブルシューティング

### コレクターがデバイスに接続できない
- SSH資格情報を確認
- `device_type` が機器に合っているか確認
- `host:port` へのネットワーク到達性を確認
- ログで具体的なエラーを確認

### Web UIに「No data available」と表示される
- コレクターが起動しているか確認
- `data/current.sqlite3` が存在するか確認
- コレクターが少なくとも1回コマンドを実行しているか確認

### 出力が長すぎる
- `max_output_lines` を調整
- `global_line_exclusions` に項目を追加

### タイムスタンプがずれている
- フロントエンドはUTCをJST（UTC+9）へ変換
- コレクターはUTCエポック秒で記録
