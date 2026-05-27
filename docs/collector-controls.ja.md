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
# コレクター制御ボタン ガイド

English: [collector-controls.md](collector-controls.md)

## 概要

Web UI には collector を制御する 3 つのボタンがあります。

- Pause Commands: コマンド収集を一時停止
- Resume Commands: 一時停止を解除
- Stop Collector: collector を安全停止

## 制御方式

- 制御状態は `control/collector_control.json` に保存
- webapp は API 経由で状態を書き込み
- collector は約 2 秒間隔で状態をポーリングして反映

## API エンドポイント

- `GET /api/collector/status`
- `POST /api/collector/pause`
- `POST /api/collector/resume`
- `POST /api/collector/stop`
- `POST /api/collector/mode`
- `POST /api/collector/run_once`

手動モードでは `manual_mode: true` が保存され、collector は通常スケジュールでのコマンド取得を停止します。Web UI に表示される `Run Commands Now` ボタンを押すと `manual_run_requested: true` が保存され、collector は次回ポーリング時に1回だけコマンド取得を実行してからリクエストをクリアします。

## 動作上の注意

- ボタン反応と collector 側反映に最大約 2 秒の差がある
- Pause 中も ping 監視は継続する
- Stop 実行後は `shutdown_requested: true` となり、collector は終了処理へ移行する

## 確認ポイント

- `control/collector_control.json` の更新時刻
- collector ログに以下の文言が出ているか
- `Command execution paused via control state.`
- `Command execution resumed via control state.`
- `Shutdown requested via control state.`
