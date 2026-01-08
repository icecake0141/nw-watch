# nw-watch - デュアルデバイス ネットワークCLIモニター

Python製のネットワーク監視システムです。複数のネットワーク機器へSSHで接続し、コマンド出力とpingデータを収集し、差分表示に対応したリアルタイムWebインターフェースで確認できます。

> 英語: [README.md](README.md) / Web UI スクリーンショット: [docs/webui-screenshots.md](docs/webui-screenshots.md)

## 特徴

- **複数デバイスのSSH収集**: 複数のネットワーク機器へ並列接続しコマンドを実行
- **継続的なping監視**: 1秒間隔で接続性を監視
- **リアルタイムWebインターフェース**: FastAPI製の自動更新UI
- **コマンド履歴**: デバイス／コマンドごとに最新10件を保持
- **差分ビュー**: 
  - 同一デバイスの前回 vs 最新出力を比較
  - 同一コマンドのデバイス間出力を比較
- **出力フィルタリング**: 
  - 特定の文字列を含む行を除外
  - エラーパターンで出力を「フィルタ済み」扱いに
  - 長い出力を設定行数でトリミング
- **時系列pingデータ**: 成功率とRTTのメトリクスを表示
- **JSTタイムゾーン表示**: すべてのタイムスタンプを日本標準時で表示

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

SQLiteを使用し、以下のスキーマを持ちます:

- **devices**: デバイス登録（id, name）
- **commands**: コマンド登録（id, command_text）
- **runs**: コマンド実行履歴
  - ts_epoch: タイムスタンプ（UTC秒）
  - output_text: 処理後のコマンド出力
  - ok: 成否フラグ
  - error_message: 失敗時のエラー詳細
  - duration_ms: 実行時間
  - is_filtered: フィルタパターンに該当
  - is_truncated: 出力がトリミングされた
  - original_line_count: フィルタ前の行数
- **ping_samples**: ping結果（ts_epoch, ok, rtt_ms, error_message）

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

1. **Collector** がSSH（Netmiko）でデバイスへ接続
2. ThreadPoolExecutorで並列にコマンドを実行
3. 設定に従って出力をフィルタ・トリミング
4. セッション専用のSQLite DBに保存
5. セッションDBを `current.sqlite3` へアトミックにコピー
6. **Web App** が `current.sqlite3` を読み込みFastAPIで配信
7. **フロントエンド** がAPIをポーリングしてUIを更新

### データベースライフサイクル

- 新しいセッションは `data/session_{epoch}.sqlite3` を生成
- 更新ごとに一時コピー `current.sqlite3.tmp` を作成
- 古い `current.sqlite3` を削除
- 一時ファイルを `current.sqlite3` にリネーム（アトミック操作）
- いつでも一貫したDB状態を提供

### ポーリング戦略

- **実行結果更新**: `max(1, floor(interval_seconds/2))` 秒
- **ping更新**: `ping_interval_seconds` 秒
- フロントエンドは自動更新トグルを尊重

## 動作要件

- Python 3.11+
- SSHでアクセス可能なネットワーク機器
- コマンドラインインターフェースを備えた機器

## セキュリティ考慮

**重要**: 資格情報は環境変数に保持することを推奨します。既定の設定では `password_env_key` を用いるため平文パスワードは不要です。本番運用では以下を検討してください:

- 環境変数またはシークレットマネージャーに秘密情報を保存
- 必要に応じて暗号化された設定ファイルを導入
- `config.yaml` のファイルパーミッションを制限（例: `chmod 600 config.yaml`）
- 可能であればSSH鍵認証を使用

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
