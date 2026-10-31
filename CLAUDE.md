# CLAUDE.md - 家庭菜園管理アプリ AI アシスタントガイド

このコードベースで作業する AI アシスタント（Claude など）のためのガイド。ここには毎回必要なことだけを置き、機能ごとの詳細は `docs/features.md`、領域ごとの規約は下の目次のファイルに置く。

## プロジェクト概要

**名称:** 家庭菜園管理アプリ
**タイプ:** Flask ベースの Web アプリケーション（Python 3.12、日本語UI、SQLite、パッケージ管理は uv）
**目的:** ビジュアルキャンバスレイアウト、日記エントリ、作物と場所の関係を使用した家庭菜園の栽培管理
**利用想定:** 自宅 LAN 内で動かし、PC と LAN 内のスマホから使う。閲覧は誰でも、登録・編集・削除はパスキーでログインした自分だけ。インターネット公開・複数人での編集は想定外。2026-10-11 から本番は Ubuntu サーバー（<サーバーのIP>、`garden-app.service`、`/opt/garden-app`）で動いており、メイン PC は開発用（`instance/garden.db` は本番データではない）。手順は `docs/api/migration-to-ubuntu.md`。待ち受けアドレスは `.env` の `HOST`（既定 `127.0.0.1`）

### 守ること

- **リポジトリは公開**。文書・コミットに実環境の固有値（IP アドレス、ユーザー名、ホスト名、ローカルのパス）を書かず `<サーバーのIP>` などの記号で書く。実際の値はリポジトリの外の `../garden-app-private/local-env.md`
- ネットワーク・セキュリティ関連の変更では、スマホからの利用（写真プールへのアップロード等）を壊さないか確認する。画像まわりを変えるときは API 側（`app/api/images.py`）も確認する
- **ログインの前提を崩さない**: パスキーの非常口（サーバーで出す1回限りの登録用 URL）が自分だけのものである根拠は、Hermes の実行ユーザーが sudo をパスワード無しで使えないことと、Hermes が 443 番に届かないこと。`NOPASSWD` を足す、Hermes の遮断を外す、Caddy の転送先を増やす、といった変更をしない（`docs/features.md` の「ログイン（パスキー）」）
- **Hermes は API だけで完結させる**: サーバーの Hermes は Web 画面（5000番）と `/opt/garden-app`（`uploads/` を含む）に触れない（ufw と権限で遮断）。Hermes にさせる機能は `/api/v1/*` だけで完結させ、画像は `/image` エンドポイントで渡す。アプリがサーバーから外へ接続する処理（OGP 取得など）を API から使うときは遮断の抜け道にしない（例: `fetch_ogp(public_only=True)`）。Hermes の API Server（8642番）を LAN に開けない。サーバーに常駐するソフトを足すときは、Hermes の実行ユーザーがそれを経由して遮断をすり抜けられないかを確かめる（例: Caddy の管理用 API は `admin off`）

### 主な機能

詳細（実装の場所・設定・決めごと）は `docs/features.md` の同じ名前の節。

- **作物・品種:** 作物（トマトなど）と品種（アイコ・桃太郎など）の CRUD。1作物：多品種、品種の外観は未設定なら作物から継承（下の「作物と品種のデータモデル」）
- **場所・見取り図:** 畑・プランターの CRUD と、作物アイコンを並べる見取り図エディター・プレビュー（過去の配置の再現あり）→ `app/static/js/CLAUDE.md`
- **植え付け・栽培記録・収穫記録:** 植え付けの状態（栽培中/栽培終了/削除済み）、観察記録、複数回の収穫。どちらもまとめて登録（`/plantings/bulk/new`、`/harvests/bulk/new`）がある
- **日記・タスク・料理記録:** 作物・品種・場所・植え付けなどとの多対多の関連付け（カード型モーダル `entity-select-modal.js`）
- **画像:** 各データへの画像添付、HEIC は JPEG に変換、GPS は外して保存、一覧はサムネイル。スライドショー → `docs/frontend/images-and-photo-pool.md`
- **写真プール・写真の振り分け:** スマホの写真を先にまとめてアップロードし、後から各データに使う（`/photo_pool/`）。1枚ずつ続けて登録する振り分け画面（`/photo_pool/sort/`）と AI 下書き
- **AIメモ下書き:** 作物・品種のメモを Claude API で下書き（地域は `/settings/`、Web 検索併用、架空の URL 対策あり）→ `docs/frontend/ai-notes.md`
- **補足情報:** 詳細画面に補足テキスト・画像・URL（OGP）・YouTube を添付 → `docs/frontend/supplements.md`
- **メモの Markdown 表示:** 詳細画面のメモをサーバー側で HTML に変換（Jinja フィルター `markdown`）→ `docs/frontend/markdown-notes.md`
- **一覧・詳細の共通部品:** バッジフィルター（`badge-filter.js` / `date-badge-filter.js`）、詳細画面の前後ナビ（`_detail_nav.html` + `get_adjacent()`）→ `docs/frontend/list-filtering.md`、`docs/frontend/detail-pages.md`
- **ダッシュボード・カレンダー:** 統計・最近の記録・画像カルーセル、月別カレンダー → `docs/frontend/dashboard.md`
- **ログイン（パスキー）:** 閲覧は `http://<サーバーのIP>:5000`（誰でも閲覧専用）、編集は `https://<サーバーのホスト名>.local/`（Caddy）でパスキーでログイン。`app/auth.py` が GET・HEAD・OPTIONS 以外を既定で拒否し CSRF を照合。テンプレートの編集の入口は `is_owner()` で囲む（`app/templates/CLAUDE.md`）
- **外部API（エージェント連携）:** `/api/v1/*` の JSON API（参照・作成・部分更新、削除なし、Bearer トークン）。`server.py` が別ポート（`API_PORT`、既定5001）で `create_api_app()` を起動 → `docs/api/README.md`、Hermes 用のスキルは `docs/api/hermes-skill/SKILL.md`
- **Hermes との連携:** 詳細画面の「Hermes に聞く」パネル、`/hermes/chat/` のチャット、`/conversations/` の会話の履歴（Matrix・アプリの会話をサーバーのタイマーで取り込み）、`/advices/` のアドバイス → `docs/frontend/hermes-ask-panel.md`、`docs/frontend/hermes-chat.md`、`docs/api/hermes-*.md`。スマホから Hermes へは LAN 内の Matrix（Element X）→ `docs/api/hermes-local-chat.md`

---

## ディレクトリ別ガイドへの目次

機能単位の詳しい規約は以下を参照（Claude Code は該当ディレクトリを触るときに自動で読み込む）。

| ファイル | カバー範囲 |
|---------|-----------|
| `docs/features.md` | 機能ごとの実装の場所・設定・決めごと。作業する機能の節だけ読む |
| `app/models/CLAUDE.md` | データベーススキーマ、テーブル/VIEW定義、`_CV_JOIN`、モデル層の実装規約、SQLite Row の重複カラム名問題 |
| `app/routes/CLAUDE.md` | URL設計、Blueprint規約、新機能追加チェックリスト |
| `app/templates/CLAUDE.md` | 編集の入口を `is_owner()` で囲む規約、トピック別ガイド（`docs/frontend/*.md`）へのインデックス |
| `app/static/js/CLAUDE.md` | 見取り図機能（エディター・プレビュー・フルスクリーン・800×800px座標系）、植え付け登録フロー |
| `docs/api/README.md` | 外部API（`app/api/`）の仕様・項目・エラー形式。API を変えたら更新する |

---

## プロジェクト構造

個々のファイルの一覧は各ディレクトリの一次情報（`app/models/CLAUDE.md` のテーブル一覧表、`app/routes/CLAUDE.md` のURL設計表、`app/templates/CLAUDE.md` のガイド一覧表）を参照。新機能を1つ追加すると、通常は `app/models/{feature}.py`, `app/routes/{feature}_routes.py`, `app/templates/{feature}/{list,detail,form}.html`, （任意）`app/static/css/{feature}.css`, （任意）`app/static/js/{feature}.js` が1セットで増える。

```
garden-app/
├── app/
│   ├── __init__.py   # Flaskファクトリ、ダッシュボード(index)ルート
│   ├── config.py / database.py / schema.sql / auth.py
│   ├── api/          # 外部API（/api/v1/*、create_api_app 専用）
│   ├── models/       # 静的メソッドパターンのモデル（{feature}.py）
│   ├── routes/       # Blueprint（{feature}_routes.py、名前は原則複数形）
│   ├── utils/        # アップロード、サムネイル、OGP、AI、Hermes の中継など
│   ├── migrations/   # 増分SQL（連番ファイル名）
│   ├── templates/    # base.html、_macros.html、_*.html（共通部品）、{feature}/
│   └── static/       # css/、js/、images/、uploads/（機能ごとのフォルダ＋thumbs/）
├── docs/             # features.md、frontend/（画面のトピック別ガイド）、api/（API の仕様・サーバーの手順）
├── tests/            # pytest（conftest.py のフィクスチャで使い捨て DB）
├── tools/            # 補助スクリプト（会話の同期、アイコン作成など）
├── instance/         # garden.db
├── run.py            # 開発サーバー（Web のみ、debug）
└── server.py         # waitress（Web :5000 ＋ API :API_PORT）
```

## 開発サーバー起動・テスト

```bash
uv run python run.py
uv run pytest
```

テストは `tests/conftest.py` のフィクスチャで tmp_path 上の使い捨て DB を使う（`instance/garden.db` には触れない）。Claude API はフェイククライアントで差し替え、実 API は呼ばない。

## 本番への反映

PR は**サーバーで動作を確かめてからマージする**（2026-10-26 から）。PR を作る → サーバーを PR のブランチに切り替えて確かめる（直すときは同じ PR にコミットを足す）→ マージ → サーバーを main に戻す。手順と取りやめるときの戻し方は `docs/api/migration-to-ubuntu.md` の「9. 更新の手順」。マージはユーザーが GitHub で行う。

---

## 作物と品種のデータモデル

作物（`crops`）と品種（`varieties`）は 1:多 の別テーブル。アプリ全体のクエリ・継承・表記に影響するので概要をここに置く。VIEW の定義・`_CV_JOIN`・継承の実装箇所は `app/models/CLAUDE.md` の「crop_variety_view（VIEW）の使い方」。

- **plantings の排他ルール**: 作物として植えたら `crop_id=X, variety_id=NULL`、品種として植えたら `crop_id=NULL, variety_id=Y`（作物は品種の親を辿る）。DB の `CHECK` 制約 + `Planting._normalize_crop_variety()` で二重に保証。品種の親作物を変えても植え付け側がズレないようにするため
- **品種の外観**（`icon_path` / `image_color` / `image_path`）は nullable で、未設定なら親作物から継承（VIEW の `COALESCE`、品種画面は `Variety.apply_inheritance()`）
- **品種を消す**と、トリガー `trg_promote_variety_plantings_before_delete` で植え付けは親作物の植え付けに昇格して残る。**作物を消す**と品種・植え付けは連鎖削除
- **VIEW `crop_variety_view`**: 品種行（`crop_id=NULL`）と作物行（`variety_id=NULL`）を UNION ALL で返す。植え付け・収穫との JOIN は両側 `IFNULL(..., -1)` の `_CV_JOIN`（4ファイルにコピーあり、修正時は全部そろえる）。`cv.*` は使わず必要な列を明示する
- **「作物Xの植え付け/収穫」**は品種経由も含めるため `WHERE cv.effective_crop_id = ?` で書く（`lc.crop_id = ?` は品種経由が漏れる）
- **補足情報**: 作物全体の情報は `entity_type='crop'`、品種固有の情報は `entity_type='variety'`

---

## DBを使った検証作業

`instance/garden.db` はユーザーの**実データ**である。マイグレーション・スキーマ変更・SQLの動作確認など、DBに対して検証を行う前に必ず `../garden-app-private/docs/db-validation-safety.md` を参照すること。バックアップ手順、`WHERE`句必須ルール、テーブル再作成時の注意点などを記載している（過去のデータ消失事故を踏まえたガイドライン）。

---

## 開発の文書（非公開側）

開発の進め方・方針の文書は公開リポジトリに置かず、リポジトリの隣の非公開フォルダ `../garden-app-private/docs/` に置く（2026-10-31 から。git で管理し、コミットしたら push する。PR は不要）。公開側に置くのはアプリの使い方・動かし方・仕様（`docs/features.md`、`docs/frontend/`、`docs/api/` の手順と仕様、各 CLAUDE.md、README）だけ。

- `dev-workflow-tips.md`: 過去のセッションで得た実務ノウハウ（コピーDBでのブラウザ確認、外部 API の早期実確認、ブラウザ自動操作の注意、未インストールのツール、Codex をレビュー役にする方法など）。**作業を始める前に一読すること**
- `image-generation.md`: 既存と同じ絵柄のアイコンを作る手順とノウハウ（Codex が既定、API の `gpt-image-2` は予備。どちらも `tools/make_icon.py`）。絵の一覧は `image-catalog.html`
- `known-issues.md`: 見つかったが対応を見送った課題・改善候補の一覧。関連箇所を触るときは確認し、対応したら行を削除する
- `wishlist.md`: ユーザーがやりたいと言った作業・検証の一覧。「次に何をするか」を聞かれたら確認する
- `db-validation-safety.md`: 実データの DB を使った検証の安全手順
- `superpowers/specs/`・`superpowers/plans/`: 設計書と実装計画。**superpowers のスキルが既定で書く `docs/superpowers/...` ではなく、ここに書く**
- `api/hermes-telegram.md`・`api/hermes-model.md`: Telegram（停止済み）と Hermes のモデル選びの経緯。Hermes の自己改善の保留（`/skills pending`）の扱いは `hermes-telegram.md`

---

## セッション終了時の振り返り

機能追加・不具合修正などひとまとまりの作業を終えたら、セッションの最後に次の振り返りを行い、得た知見をドキュメントに残す。

1. **つまずき・手戻りを洗い出す**: 想定と違った挙動、やり直した作業、ユーザーに確認し直したこと、レビューで見つかった指摘を列挙する
2. **原因と再発防止策を考える**: 「次回の自分が知っていれば避けられたか」で判断する。一度きりの事情や、コード・git 履歴を読めば分かることは残さない
3. **適切な場所に残す**（1トピック1ファイルの原則に従う）:
   - 作業の進め方・環境・ツールのノウハウ → `../garden-app-private/docs/dev-workflow-tips.md`（足すときは古くなった項目を消す。仕組み（設定・スクリプト・`.gitattributes` など）で防げるものは仕組みにして、文書には書かない）
   - 見送った不具合・改善候補 → `../garden-app-private/docs/known-issues.md`
   - 特定の領域の規約・落とし穴 → 該当する CLAUDE.md または `docs/frontend/*.md`（DB は `../garden-app-private/docs/db-validation-safety.md`）
   - 機能の仕様変更 → 「ドキュメント更新チェックリスト」に従って更新
   - サーバー・端末・外部サービスの構成（常駐するソフト、ポート、ufw、つながり）が変わった・新しく分かった → リポジトリの外の `../garden-app-private/overview.html`（自分用の全体図。実際の値で書く）と `local-env.md`
4. **作業記録を書く**: リポジトリの隣のフォルダ `../garden-app-private/worklog/` に、1作業1ファイル（`YYYY-MM-DD-作業名.md`）で、やったこと・決めたこと・つまずき・次にやることを書き、そのフォルダの git にコミットする（書き方は同フォルダの `README.md`）。このフォルダは公開しない。実環境の固有値は書いてよいが、トークンなどの秘密の値は書かない
5. **ユーザーに報告する**: 振り返りの要点と、どのファイルに何を追記したかを伝える

---

## ドキュメント更新チェックリスト

機能やモデル・スキーマを変更した際は必ず以下も更新すること：

- **`docs/features.md`**: 該当機能の節（実装の場所・設定・決めごと）。新しい機能は節を足す
- **`CLAUDE.md`（このファイル）**: 「主な機能」の1行（機能を足したとき・名前や入口が変わったとき）、「守ること」・データモデルの概要に関わる変更。詳細はここに書かず `docs/features.md` へ
- **`app/models/CLAUDE.md`**: テーブル定義・カラム定義の追加・変更・削除を反映
- **`app/routes/CLAUDE.md` / `app/static/js/CLAUDE.md`**: 該当領域の規約変更を反映
- **`app/templates/CLAUDE.md` / `docs/frontend/*.md`**: 既存トピックへの追記で足りるものはそのトピックファイルを更新。新規の横断的トピックは新しいファイルを起こし、`app/templates/CLAUDE.md` のガイド一覧表に追記する（1トピック1ファイルの原則を崩さない）
- **`README.md`**: ユーザー向けの機能説明・プロジェクト構造を更新
