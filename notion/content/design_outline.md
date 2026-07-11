# 設計メモ

Gemini Enterprise Agent Platform から呼ばれる Cloud Run アプリの設計整理。
このメモは Notion へ転記する前提で、実装よりも責務と運用の見通しを優先している。

## 目的

- 検索、運用確認、同期処理を分離して扱う
- アクセス制御と監査を最優先にする
- Cloud Run 上の役割を明示して、運用時の迷いを減らす

## Cloud Run の構成

- Search API: 検索要求の受付、ACL 判定、応答整形
- Ops UI: health/runtime/chat の疎通確認
- Indexer / Connector Worker: ソース同期と再インデックス

Cloud Run アプリとしては、対話 UI を持つ確認画面と、将来の検索 API/同期ワーカーの境界を分けて考える。

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

これら 5 つの接続先は、検索対象の代表例として扱う。

## 監査

- 検索者、時刻、ソース、文書 ID、失敗理由、処理時間を残す
