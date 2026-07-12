# 0002: 認可モデルとして RBAC + ABAC を採用

## Context

エンタープライズ検索基盤では、検索クエリを投げた利用者に対して「見えてよい情報だけ」を返す必要がある。

今回の要件では、単に職種や業務ロールだけでなく、以下の属性を認可判断に利用する必要がある。

- 所属国・地域 (`region`)
- 所属部署 (`department`)
- 職位 (`position`)
- 上司 / 部下の関係 (`managerId` など)
- グループ所属 (`groups`)

また、文書ごとにも表示条件があり、検索結果側に以下のような metadata を持たせてフィルタする必要がある。

- `allowed_groups`
- `allowed_departments`
- `allowed_regions`
- `allowed_positions`
- `allowed_manager_ids`
- `allowed_user_subs`

そのため、`trader` や `hr-manager` のようなロールだけでアクセス可否を決める RBAC 単独では、要件を十分に満たせない。

## Decision

認可モデルとして、RBAC を土台にしつつ ABAC で補完する方式を採用する。

具体的には以下の方針とする。

- `groups` やロール相当の属性で大まかなアクセス範囲を絞る
- `region`, `department`, `position`, `managerId` で詳細なアクセス条件を評価する
- 文書 metadata と利用者 claims を突き合わせ、検索結果を文書単位でフィルタする
- Okta / Okta LDAP Agent の認証後に得た claims を認可判断の入力として利用する

実装上は、`allowed_groups` を RBAC 的な制御、`allowed_regions` や `allowed_manager_ids` を ABAC 的な制御として扱う。

## Consequences

- ロールだけでは表現できない「同じロールでも地域や部門で見えるものが違う」要件に対応できる
- 直属部下の HR 文書のみ見せるといった管理ラインベースの制御を表現できる
- GDPR や地域制約を `region` ベースで認可に反映できる
- 利用者属性と文書属性の両方を扱うため、RBAC 単独より実装は複雑になる
- Okta claims の設計と文書 metadata 設計が認可品質に直結する

## Notes

- この判断は「RBAC を否定する」のではなく、「RBAC 単独では不足するため ABAC を併用する」という意味である
- 固定する claims 名や metadata キーは実装と README に反映済み
- 将来的には ID Mapping やドキュメント単位の継承ルールを別 ADR に切り出す余地がある