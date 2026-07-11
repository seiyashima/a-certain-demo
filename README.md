# a-certain-demo

Cloud Run 上で動かすことを前提にした、複数 SaaS 横断検索の最小バックエンド実装です。

## できること

- FastAPI ベースの `/search` API
- `X-API-Key` による簡易認証
- HTTPS のみ・許可ホストのみへ接続する SaaS プロバイダー設定
- SaaS ごとの ****** を使ったフェデレーテッド検索
- Cloud Run 向け `Dockerfile` と `.env.example`

## セキュリティ設計の要点

- SaaS 接続先は `SEARCH_APP_ALLOWED_PROVIDER_HOSTS` で明示許可
- 各プロバイダー URL は HTTPS 必須
- API 利用者は `SEARCH_APP_API_KEY` で認証
- クエリ長と検索件数に上限を設けて過負荷を抑制
- 外部 SaaS 呼び出しはタイムアウト付きで実行

## ローカル起動

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## テスト

```bash
pytest
```
