# a-certain-demo

☁️ Cloud Run 上で動かすことを前提にした、複数 SaaS 横断検索の最小バックエンド実装です。

このリポジトリには 2 つの実装が共存しています。

- `app.py`: コネクタ統合や UI 疎通確認向けのシンプルな FastAPI ゲートウェイ
- `app/`: Okta-aware ABAC を含む Cloud Run 向け federated search backend

## ✨ できること

- 🚀 FastAPI ベースの `/search` API
- 🔐 `X-API-Key` による簡易認証
- 🌐 HTTPS のみ・許可ホストのみへ接続する SaaS プロバイダー設定
- 🔎 SaaS ごとのコネクタ設定を使ったフェデレーテッド検索
- 📦 Cloud Run 向け `Dockerfile` と `.env.example`

## 🛡️ セキュリティ設計の要点

- ✅ SaaS 接続先は `SEARCH_APP_ALLOWED_PROVIDER_HOSTS` で明示許可
- ✅ 各プロバイダー URL は HTTPS 必須
- ✅ API 利用者は `SEARCH_APP_API_KEY` で認証
- ✅ クエリ長と検索件数に上限を設けて過負荷を抑制
- ✅ 外部 SaaS 呼び出しはタイムアウト付きで実行
- ✅ API キー比較は定数時間比較を利用
- ✅ プロバイダー名重複と不正な検索パスを起動時に拒否
- ✅ Principal ごとの ACL で利用可能プロバイダーと利用上限を強制

## 🧱 バックエンド設計

- API 層: FastAPI で認証、入力検証、プロバイダー選択を実施
- 設定層: Pydantic Settings で環境変数を型安全に取り込み
- 接続層: SaaS ごとにコネクタを生成し、並列で検索を実行
- 集約層: 結果をマージし、失敗プロバイダーを `failed_providers` に返却

## 🔐 推奨運用（Cloud Run）

- `SEARCH_APP_API_KEY` や `SEARCH_APP_PROVIDERS__*__BEARER_TOKEN` は Secret Manager で管理
- Cloud Run の Ingress は内部 or LB 配下に制限（公開 API の場合は Cloud Armor を併用）
- サービスアカウントは最小権限（Secret Accessor のみなど）
- 監査ログを有効化し、4xx/5xx とレイテンシをダッシュボード化
- Okta JWT 検証を使う場合は issuer / audience / JWKS URL を固定し、Bearer token から claims を直接取り出す

## 🔑 Okta / LDAP Agent で扱う認証情報

Cloud Run 側では、Okta または Okta LDAP Agent の認証後に「ユーザー属性」と「機密値」を分けて扱う。

認証後にアプリが受け取る情報の推奨最小セット:

- `sub`: Okta が発行する不変のユーザー ID。同じ人をメールアドレス変更後も一意に追跡するための内部キー
- `email` または `preferred_username`: 表示・監査用のログイン名
- `groups`: Okta 上の所属グループ一覧。たとえば `trader`, `hr-manager`, `compliance-officer` のような権限判定の材料
- `roles`: アプリ側の coarse-grained 権限が必要な場合のみ
- `department`, `costCenter`, `region`: ABAC に必要なときのみ
- `manager` または `managerId`: HR 系の直属配下制御が必要なときのみ
- `tenant` / `org`: マルチテナント時のみ

実務上の理解:

- `sub` は「誰なのか」をぶれずに識別するための ID
- `groups` は「どの権限の箱に入っているか」を示す一覧
- `email` は人が読むための名前、`sub` はシステムが照合するための ID

今回固定する Okta claim 名:

- `sub`: ユーザーの不変 ID
- `groups`: 所属グループ
- `department`: 所属部署
- `region`: 所属国・地域
- `position`: 職位
- `managerId`: 上司または管理ライン判定に使う ID

Okta JWT 検証に使う設定:

- `SEARCH_APP_OKTA_AUTH_ENABLED`
- `SEARCH_APP_OKTA_ISSUER`
- `SEARCH_APP_OKTA_AUDIENCE`
- `SEARCH_APP_OKTA_JWKS_URL`
- `SEARCH_APP_OKTA_CLAIM_SUB`
- `SEARCH_APP_OKTA_CLAIM_GROUPS`
- `SEARCH_APP_OKTA_CLAIM_DEPARTMENT`
- `SEARCH_APP_OKTA_CLAIM_REGION`
- `SEARCH_APP_OKTA_CLAIM_POSITION`
- `SEARCH_APP_OKTA_CLAIM_MANAGER_ID`

Bearer token を使う場合:

- `Authorization: Bearer <token>` を受け取る
- アプリは JWKS で署名検証し、claims を `AuthContext` に正規化する
- `SEARCH_APP_OKTA_AUTH_ENABLED=true` のときは Bearer token があればそちらを優先する
- Bearer token が無い場合は既存の `X-User-*` ヘッダー入力へフォールバックできる

保持しない方がよい情報:

- パスワード
- LDAP bind password
- 長期 refresh token
- 全属性ダンプ
- ACL 判定に不要なプロフィール属性

Okta LDAP Agent を使う場合の考え方:

- LDAP 認証そのものは Okta 側で終わらせる
- Cloud Run は LDAP に直接 bind しない
- Cloud Run は Okta から渡された claims のみを信頼する
- LDAP の生属性は Okta 側で必要最小限の claims に正規化してから渡す

## 🗄️ Secret Manager に入れるもの / 入れないもの

Secret Manager に入れるもの:

- Okta OIDC client secret
- SaaS provider bearer token
- 将来必要なら token exchange 用 client secret
- 例外的に必要な LDAP bind secret

Secret Manager に入れないもの:

- `sub`, `email`, `groups` などのユーザー claims
- `manager`, `department`, `region` などの認可属性
- JWT 自体
- ACL 判定結果のキャッシュ

管理場所の推奨:

- 機密値: Secret Manager
- issuer URL, audience, claim mapping 名称: 環境変数または設定ファイル
- ユーザー claims: リクエストごとの JWT / ID token / access token 由来
- ACL マッピング: アプリ設定またはインデックス側メタデータ

この構成にすると、Secret Manager は「静的な秘密」だけを持ち、ユーザーごとに変わる属性はトークンから毎回評価する形になる。

## ⚙️ 環境変数

`.env.example` の主な項目:

- `SEARCH_APP_API_KEY`: クライアント認証用の共有鍵
- `SEARCH_APP_ALLOWED_PROVIDER_HOSTS`: 接続許可ホストのカンマ区切り
- `SEARCH_APP_REQUEST_TIMEOUT_SECONDS`: SaaS 呼び出しタイムアウト秒
- `SEARCH_APP_MAX_QUERY_LENGTH`: クエリ長上限
- `SEARCH_APP_MAX_RESULTS_PER_PROVIDER`: 1 プロバイダーあたり取得上限
- `SEARCH_APP_PROVIDERS__N__*`: N 番目の SaaS プロバイダー定義
- `SEARCH_APP_ACL_ENABLED`: ACL 有効化 (`true`/`false`)
- `SEARCH_APP_ACL_POLICIES__N__*`: N 番目の ACL ポリシー定義

ACL ポリシー項目:

- `PRINCIPAL`: クライアント識別子（`X-Client-Id` と一致）
- `ALLOWED_PROVIDERS`: 利用可能なプロバイダー名（カンマ区切り）
- `ALLOWED_GROUPS`: `trader`, `hr-manager`, `compliance-officer` などの所属グループ
- `ALLOWED_DEPARTMENTS`: `hr`, `compliance`, `markets` などの所属部署
- `ALLOWED_REGIONS`: `apac`, `emea`, `amer` などの所属国・地域
- `ALLOWED_POSITIONS`: `manager`, `individual-contributor` などの職位
- `REQUIRE_MANAGER`: 上司コンテキスト必須かどうか
- `MAX_QUERY_LENGTH`: Principal 単位クエリ長上限（省略時は全体設定）
- `MAX_RESULTS_PER_PROVIDER`: Principal 単位の結果件数上限（省略時は全体設定）

## 🔎 ACL の管理とチェック

- 管理: ACL は環境変数で宣言的に管理（Cloud Run では revision ごとに反映）
- 強制: `/search` は `X-Client-Id` に加えてユーザー属性ヘッダーを受け取り、ACL / ABAC 違反時は `403` を返却
- 検証: `/acl/check` で principal の許可範囲を事前確認可能

`/search` や `/acl/check` で評価する主な属性:

- `X-User-Groups`: カンマ区切りのグループ一覧
- `X-User-Department`: 所属部署
- `X-User-Region`: 所属国・地域
- `X-User-Position`: 職位
- `X-User-Manager-Id`: 上司コンテキスト判定用

今回の設計では、認可判断に以下を使えるようにしている:

- どの国・地域に所属しているか
- どの部署に所属しているか
- 上司か部下かに関わる職位・管理者コンテキスト
- どの権限グループに所属しているか

検索結果 metadata で使うキー:

- `allowed_groups`
- `allowed_departments`
- `allowed_regions`
- `allowed_positions`
- `allowed_manager_ids`
- `allowed_user_subs`

この metadata を各文書または検索インデックスに保持すると、呼び出し元 claims と突き合わせて文書単位の表示可否を決められる。

`/acl/check` 例:

```bash
curl -X POST http://localhost:8080/acl/check \
	-H 'content-type: application/json' \
	-H 'x-api-key: replace-with-a-long-random-shared-secret' \
	-d '{"principal":"web-client","providers":["docs","tickets"],"query_length":90}'
```

## ⚙️ ローカル起動

シンプルゲートウェイを動かす場合:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

federated search backend を動かす場合:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## 🧪 ETL デモ用モックモード

デモ用途では、5システム接続、Secret Manager 参照、LDAP bind 情報取得を実接続せずにモック応答で実行できる。

- `SEARCH_APP_ETL_ENABLED=true`
- `SEARCH_APP_ETL_MOCK_MODE=true`

この設定では、`/etl/run` は外部SaaSや Discovery Engine API へ接続せず、固定データを使って Extract/Transform/Load を完了する。

モック確認用エンドポイント:

- `GET /mock/systems/{system_name}/records`: 5システムの固定レコードを返す
- `POST /mock/idp/{identity_provider}/token?system={system}`: Okta / Entra ID / Okta LDAP Agent 用の固定トークンを返す
- `GET /mock/secrets/{secret_name}`: Secret Manager 相当の固定シークレットを返す
- `GET /mock/ldap/bind/compliance-system`: LDAP bind 情報の固定値を返す

## 🗂️ 今回の設計変更の反映一覧

1. ETL を Extract / Transform / Load に分割
実装反映: `app/etl/extract.py`, `app/etl/transform.py`, `app/etl/load.py`, `app/etl/pipeline.py`

2. 5システム個別連携
実装反映: `.env.example` の `SEARCH_APP_ETL_SYSTEMS__N__*`、`app/config.py` の `ETLSystem`

3. 認証方式切替（Okta / Okta LDAP Agent / Entra ID）
実装反映: `app/config.py` の `identity_provider`、`app/etl/extract.py` の認証分岐

4. Transform で Document 化 + ACL 付与
実装反映: `app/etl/transform.py` の `DiscoveryDocument` と `acl` 正規化

5. Load を Discovery Engine API + BigQuery 宛先で統一
実装反映: `app/etl/load.py`、`SEARCH_APP_ETL_DISCOVERY_ENGINE_LOAD_URL`、`SEARCH_APP_ETL_BIGQUERY_TABLE`

6. デモ時は外部接続せずモック応答に切替
実装反映: `SEARCH_APP_ETL_MOCK_MODE`、`app/etl/mock_data.py`、`/mock/*` API（`app/main.py`）

## シンプルゲートウェイ API

- Health check endpoint: `/healthz`
- Search gateway endpoint: `POST /api/search`
- Connector catalog endpoint: `GET /api/connectors`
- Browser UI for manual checks and search routing

検索例:

```bash
curl -s -X POST http://127.0.0.1:8080/api/search \
	-H 'Content-Type: application/json' \
	-H 'X-Request-Id: demo-001' \
	-d '{"subject":"admin-user","query":"runbook policy incident","target_system":"all"}'
```

## 🧪 テスト

```bash
pytest
```

## ☁️ Cloud Run デプロイ例

```bash
gcloud run deploy federated-search-api \
	--source . \
	--region asia-northeast1 \
	--allow-unauthenticated \
	--set-env-vars SEARCH_APP_ALLOWED_PROVIDER_HOSTS=docs.example.com,tickets.example.com,SEARCH_APP_REQUEST_TIMEOUT_SECONDS=5,SEARCH_APP_MAX_QUERY_LENGTH=120,SEARCH_APP_MAX_RESULTS_PER_PROVIDER=10
```

運用では機密値を `--set-secrets` で渡してください。

## Notion Integration

The Notion integration is split into three layers:

- `notion/client.py`: API access and page operations
- `notion/content/design_outline.md`: editable design memo source
- `notion/actions/publish_design.py`: runtime command that publishes the memo to Notion

Create a local `.env` file from `.env.example` and set the Notion variables.

```sh
cp .env.example .env
```

To verify the configured page title:

```sh
python3 -m notion
```

To append the design outline blocks to the target page:

```sh
NOTION_ACTION=publish_design python3 -m notion
```

Do not commit `.env` or any real token values.
