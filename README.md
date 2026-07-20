# a-certain-demo

Cloud Run 上で動かすことを前提にした、複数 SaaS 横断検索と ETL デモを扱うサンプルリポジトリです。

このリポジトリは、検索 API の最小実装、Cloud Run を前提にした設計資料、Notion 連携用の補助スクリプトをまとめた案内入口として使います。

## リポジトリの見どころ

- `app.py`: UI 疎通確認向けのシンプルな FastAPI ゲートウェイ
- `app/`: ACL / ABAC と ETL を含む Cloud Run 向け backend
- `design/`: 公開用の設計書、アーキテクチャ図、シーケンス図
- `notion/`: 設計メモを Notion に反映するための補助コード
- `tests/`: API と ETL のテスト

## できること

- SaaS 横断の検索 API を試せる
- ACL / ABAC を含む検索 backend の構成を確認できる
- ETL の mock mode で外部接続なしのデモを実行できる
- 設計資料と Mermaid 図をまとめて参照できる

## まず見る場所

- `design/index.html`: 設計ドキュメントの入口
- `design/system-overview.html`: システム全体の概要
- `design/connector-architecture.html`: Connector / ETL 側の考え方
- `.env.example`: 必要な設定項目の一覧

## ローカル起動

### シンプルゲートウェイ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Federated search backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## テスト

```bash
python -m pytest
```

## 補足

- 詳細な設計判断や仕様メモは `design/` と `notion/` 配下で管理しています
- 機密値や実トークンはリポジトリに含めず、ローカル `.env` または Secret Manager を使ってください
