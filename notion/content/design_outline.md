# 設計メモ

Gemini Enterprise Agent Platform から呼ばれる Cloud Run アプリの設計整理。

## 目的

- 検索・運用確認・同期処理を責務分離して実装する
- アクセス制御と監査を最優先にする

## Cloud Run の構成

- Search API: 検索要求受付、ACL 判定、応答整形
- Ops UI: health/runtime/chat の疎通確認
- Indexer / Connector Worker: ソース同期と再インデックス

## 認証・認可

- Okta SSO を起点にする
- WIF を利用し、長期資格情報を保持しない
- 元システムの ACL を検索結果に反映する

## 接続先

- ServiceNow
- Workday
- Compliance System
- SharePoint
- Confluence

## 監査

- 検索者、時刻、ソース、文書 ID、失敗理由、処理時間を残す
