# nw-watch - デュアルデバイス ネットワークCLIモニター

Python製のネットワーク監視ツールです。複数のネットワーク機器へSSHで接続し、コマンド出力とping結果を収集してWeb UIでリアルタイム表示・差分確認ができます。

## 主な機能

- 複数デバイスへの並列SSH接続とコマンド実行
- 1秒間隔の継続的なping監視（成功率・RTT表示）
- FastAPI製Web UIによるリアルタイム表示と自動更新
- コマンド実行履歴の保持（最新10件）
- 直前比較およびデバイス間比較の差分ビュー
- フィルタリング／トリミングによる出力整理

## クイックスタート

1. 依存関係をインストール

   ```bash
   pip install -e ".[dev]"
   ```

2. 設定ファイルを作成

   ```bash
   cp config.example.yaml config.yaml
   # パスワードは環境変数で指定
   export DEVICEA_PASSWORD="password123"
   export DEVICEB_PASSWORD="password123"
   ```

3. コレクターを起動（コマンド・pingの収集）

   ```bash
   python -m collector.main --config config.yaml
   ```

4. Webアプリを起動（別ターミナルで実行）

   ```bash
   uvicorn webapp.main:app --reload --host 127.0.0.1 --port 8000
   ```

   ※ `--reload` は開発向けの自動リロードオプションです。本番運用では省略し、プロセスマネージャーなどで常駐させてください。

5. ブラウザでUIへアクセス

   ```
   http://127.0.0.1:8000
   ```

## 追加ドキュメント

- Web UIの機能説明とスクリーンショット: [`docs/webui-screenshots.md`](docs/webui-screenshots.md)
- アーキテクチャ、セキュリティ、トラブルシューティング、ライセンスの詳細: [README.md](README.md)

## テスト

```bash
pytest
```
