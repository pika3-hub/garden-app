# 機能の詳細（実装の場所と決めごと）

ルート `CLAUDE.md` の「主な機能」の詳しい版。機能ごとの実装の場所・設定・決めごと（なぜそうしたか）を書く。
作業する機能の節だけ読めばよい。機能を足したり変えたりしたら、ここの該当の節とルート `CLAUDE.md` の1行を直す。

## 作物管理

作物（トマト、なすなど）のCRUD。種類・アイコン・イメージカラー・画像・Markdownメモを持つ

## AIメモ下書き

作物・品種フォームの「✨ AIで下書き」から Claude API でメモの下書き（設定画面の地域・栽培環境を基準にした時期、特性、栽培のコツ）を生成し、モーダルで確認して置き換え／追記できる。「Webで調べる」（品種は既定ON）で Web 検索を併用し参考URLを付与（`web_search_20260209` は本文に citations が付かないことが多いため、参考にしたページを AI に `## 参考URL` として書かせ、検索結果・citations に実在する URL だけを検索結果のタイトルで残す（架空の URL 対策）。AI が書かなかったときだけ citations の URL を使う。検索結果の上位をそのまま付けると読んでいないページが混ざるので付けない）。APIキーは `.env` の `ANTHROPIC_API_KEY`、モデルは `ANTHROPIC_MODEL`（`claude-opus-5-5` 既定 / `claude-sonnet-5-5` / `claude-haiku-5-5`。Haiku はサーバー側フォールバック非対応・`web_search_20260209` 非対応のため、`MODEL_INFO` の設定でフォールバックを付けず `web_search_20250305` を使う）。地域は設定画面（`/settings/`）で `app_settings` テーブルに保存。実装は `app/utils/ai_notes.py` + `settings_routes.py` + `_ai_notes_button.html` / `_ai_notes_modal.html` / `ai-notes.js`。Hermes から作物・品種を登録するときも、`hermes-skill/SKILL.md` の指示で同じ形式のメモを書かせている（地域は `GET /api/v1/meta` の `region`。参考URLは本文に残す。補足情報（`extra_urls` / `extra_youtube`）には写さず、地域を入れずに一般的な育て方で別に探した Web ページ・YouTube を付けさせる（2026-10-25 のユーザーの希望。メモは地域込み、補足情報は一般的な情報））

## 品種管理

作物に紐づく品種（アイコ、桃太郎など）のCRUD。1作物：多品種の関係。アイコン・イメージカラー・画像は nullable で、未設定時は親作物から継承

## 場所管理

畑やプランターの場所のCRUD、画像サポート付き

## キャンバスエディター

バニラJSベースのビジュアル菜園レイアウトデザイナー（作物アイコンのドラッグ&ドロップ配置、背景画像選択）。植え付け登録時に見取り図配置ページへ自動遷移（スキップ可能）

## 見取り図プレビュー

場所詳細・植え付け詳細に読み取り専用の見取り図を表示（植え付けのハイライト・ディム対応）、場所詳細ではフルスクリーン表示の日付ナビゲーション（前へ/次へ・左右キー）で過去の配置状態を再現可能

## 栽培記録

作物と場所をリンクし、ステータス追跡（栽培中/栽培終了/削除済み）、タブフィルター付き一覧（`/plantings/`）、栽培観察記録の登録・管理。植え付け一覧の「栽培記録をまとめて登録」から複数の植え付けの栽培記録を一括登録も可能（`/plantings/bulk/new`）：複数の植え付けを選択→共通の記録日・既定画像を設定した上で、メモ・画像は植え付けごとに個別入力・上書き（写真プールからの選択も可）できる

## 収穫記録

複数回の収穫を記録、収穫量・単位・メモ・画像対応、植え付けからの日数自動計算。収穫一覧・植え付け詳細の両方から「収穫を記録」可能で、新規フォームはモーダルから対象の植え付けを選択できる（種類・場所バッジフィルタ付き）。収穫一覧の「まとめて登録」から一括登録も可能（`/harvests/bulk/new`）：複数の植え付けを選択→共通の収穫日・既定画像を設定した上で、収穫量・単位・メモ・画像は植え付けごとに個別入力・上書き（写真プールからの選択も可）できる

## 日記システム

複数エンティティ（作物、品種、場所、植え付け、収穫）との関連付けと画像添付を持つ栽培日記。関連付けはカード型モーダルで複数選択（`entity-select-modal.js`）

## 画像サポート

作物・品種・場所・栽培記録・収穫・日記・料理・補足情報の画像アップロード・管理（PNG/JPG/GIF/WebP。HEIC/HEIF は中身で判定して JPEG に変換して保存（`pillow-heif`、EXIF・色プロファイルは残す）。撮影場所（GPS）は JPEG・HEIC から外して保存（`app/utils/strip_gps.py`）。1リクエスト合計最大256MB＝写真プールの一括アップロード対応）、一覧画面はサムネイル（800×600px JPEG）を使用して高速化

## スライドショー

栽培記録一覧（植え付け詳細内）・収穫記録一覧の画像をフルスクリーンで閲覧（`slideshow.js` + `slideshow.css`）、日付・日数・キャプション表示、キーボード操作対応

## メモの Markdown 表示

詳細画面のメモ・本文・補足テキスト・サイドバーの作物/品種/場所カードは、入力された Markdown をサーバー側で HTML に変換して表示（`markdown-it-py`、Jinja フィルター `markdown`、生 HTML はエスケープ、単独改行も維持）。一覧などの切り詰めプレビューはプレーンテキストのまま。詳細は `docs/frontend/markdown-notes.md`

## 検索とフィルター

作物・品種・場所・植え付け・収穫・料理の一覧はクライアントサイドの種類バッジフィルター（`badge-filter.js`）、日記・タスクはクライアントサイドの年・季節・月バッジフィルター（`date-badge-filter.js`）。日記・タスク・料理はサーバーサイドのキーワード検索も持つ

## ダッシュボード

統計情報と最近のアクティビティ概要、画像カルーセル（全データ種別の最近の画像をランダム再生、Bootstrap 5 Carousel使用）

## カレンダービュー

月別カレンダーで作物・品種・場所・日記・植え付け・栽培記録・収穫・タスク・料理をアイコン表示、詳細ページへのリンク

## タスク管理

栽培作業タスクのCRUD、ステータス管理（未着手/進行中/完了）、期限日設定、作物・品種・場所・植え付けとの関連付け。関連付けはカード型モーダルで複数選択（`entity-select-modal.js`）

## 詳細画面ナビゲーション

全詳細画面（作物・品種・場所・植え付け・栽培記録・収穫・日記・タスク・料理）で前後データへの移動ボタンを表示。共通部品 `_detail_nav.html` を使用し、各モデルの `get_adjacent()` メソッドで一覧の表示順に基づく前後を取得

## 補足情報

作物・品種・場所・日記・タスク・収穫・料理の詳細画面に補足テキスト、追加画像、外部URL（OGP情報の自動取得付き）、YouTube動画埋め込みを複数添付可能。共通テンプレート `_supplements_section.html` + `supplements` テーブルで管理

## 写真プール

モバイルで撮影した複数写真を先に一括アップロードし、後から各写真を選んで作物・品種・場所・栽培記録・収穫・料理・日記・補足情報の登録/編集画面へ送り込める機能（`/photo_pool/`）。プール写真は `uploads/photo_pool/` に独立保存し、登録時に対象エンティティのフォルダへコピー（使い回し可）。使用回数は `photo_pool_usages` 中間テーブルで追跡。各登録/編集画面の画像フィールドからは「写真プールから選択」ボタンで共通モーダル（`_photo_pool_picker_modal.html`）を開いて選択可能（ローカルファイル選択と排他UI、使用状況フィルター付き）。一覧の各写真には使用先（登録したデータ）へのリンクを出す（`PhotoPool.get_usage_links()`。補足情報は親の詳細画面へ、削除済みは「削除済み」）

## 写真の振り分け

写真プールで複数枚を選び「選んだ写真を振り分ける」→ 1枚ずつ大きく見ながら種類（栽培記録・収穫・料理・日記・植え付け＋栽培記録・作物・品種・場所）と対象を選んで登録し、「保存して次へ」で写真プールに戻らず続ける（`/photo_pool/sort/`、Blueprint `photo_sort`。状態は URL の `ids` / `pos` / `done` / `kind` だけで持つ）。「保存して、この写真で続けて登録」で同じ写真を別の行き先にも使える。栽培記録・収穫は植え付けを複数選べ（メモは共通、収穫量・単位は植え付けごと）、植え付けは最初の栽培記録に写真を付ける（見取り図の配置には移らない）。「✨ AIで下書き」（ボタンを押したときだけ）は写真のサムネイルを Claude API に送り、種類ごとの項目（メモ、料理のタイトル・カテゴリ、日記のタイトル・本文）を下書きする。栽培記録は「前回からの変化も書く」（既定オン）なら、植え付けごとに写真のある前回の栽培記録の写真とメモ（写真の補助）も送って変化を書かせる。アドバイスは書かせない（`app/utils/ai_photo_drafts.py`。`output_config.format` の JSON で受け取る。作物・品種は既存の AI メモ下書き）。補足情報（画像）への振り分けは未対応（`../garden-app-private/docs/wishlist.md`）

## 料理記録

収穫した野菜を使った料理のCRUD（`/cooking/`）。タイトル・カテゴリ・調理日（必須）・メモ・画像を記録。作物・品種・植え付け・収穫との多対多関連付け（`cooking_relations` テーブル）。補足情報対応（`entity_type='cooking'`）。メニュー順は収穫の直後

## Hermes に聞くパネル

植え付け・作物・品種の詳細画面（ログイン中かつ `HERMES_API_KEY` 設定済みのときだけ）の右下の「Hermes に聞く」から開く右側のパネル（Bootstrap offcanvas）で Hermes に相談・依頼できる。開いている画面（種類・id・表示名・読む API）を Hermes への instructions に載せるので主語を省いた質問ができ、画面（データ）ごとに別の会話（`hermes_chats` 表の `session_id`、「新しく始める」で変わる）が後日も続く。ブラウザはアプリの中継 `/hermes/ask/...`（`hermes_ask_routes.py`、全てログイン必須・CSRF 照合）にだけ話し、アプリが Hermes の API Server（`HERMES_API_URL` 既定 `http://127.0.0.1:8642`、`HERMES_API_KEY`＝Hermes の `API_SERVER_KEY`）の events（SSE）を中継する。キーは HTML・JS・JSON に出さない。道具は Element X と同じ（絞らない）で、承認待ちはパネルで `once` / `deny` だけ返す。パスキーでログインした人は Hermes にできることを何でも頼めるので、8642 番を LAN に開けない。会話は同期で `/conversations/` にも並ぶ。実装は `app/utils/hermes_client.py` + `hermes_context.py` + `app/models/hermes_chat.py`（マイグレーション 026）+ `_hermes_ask_panel.html` + `hermes-ask.js`。画面の部品は `docs/frontend/hermes-ask-panel.md`、本番の設定は `docs/api/hermes-ask-panel.md`、設計は `../garden-app-private/docs/superpowers/specs/2026-10-29-hermes-ask-panel-design.md`。Hermes への指示は `hermes-skill/SKILL.md` の「アプリのパネルからの相談」

## Hermes とのチャット

ログイン中かつ `HERMES_API_KEY` 設定済みのとき、ナビの「Hermes」が開く `/hermes/chat/`（Blueprint `hermes_chat`、Hermes の各ページの最初のタブ「チャット」）で、見ているデータの無い自由な会話を複数持てる（Element X のようなチャット）。パネルの会話も一覧に並び、続きを話せる。題名の変更と削除ができ、削除はアプリの中だけ（チャット一覧と `/conversations/` から消え、`deleted_conversations` 表に覚えて同期 API が削除済みの会話とその続きを無視する。Hermes の `state.db` の記録と保存済みのアドバイスは残る）。ログアウト中はナビが `/conversations/` に行き、チャットのタブは出ない。中継はパネルと同じ `/hermes/ask/...`（会話の行の id で扱うルートを追加）。実装は `app/routes/hermes_chat_routes.py` + `hermes_chat/index.html` + `hermes-chat.js` + `hermes-chat.css`、指示は `hermes_context.py` の `_INSTRUCTIONS_CHAT`。画面の部品は `docs/frontend/hermes-chat.md`、設計は `../garden-app-private/docs/superpowers/specs/2026-10-30-hermes-chat-design.md`。Hermes への指示は `hermes-skill/SKILL.md` の「チャット画面からの相談」

## Hermes との会話の履歴

サーバーの Hermes と Matrix（Element X）またはアプリのパネルでした会話（経路は `conversations.source` の `matrix` / `api_server`。一覧・詳細に「アプリ」「Element X」の印と、パネルの会話は対象のデータを出す）を、アプリの `/conversations/`（新しい順、キーワード検索）と会話の詳細（ユーザーの発言と Hermes の返事の文章、縮小版の写真、Hermes が curl で作った・変えた・見たデータへのリンク）で見られる。作物・品種・場所・植え付け・栽培記録・収穫・日記・タスク・料理の詳細画面にも「このデータが出てきた Hermes との会話」の欄（`_hermes_conversations_section.html`、Jinja グローバル `hermes_conversations`）を出す。取り込みは `tools/hermes_conversation_sync.py`（サーバーの Hermes の実行ユーザーが systemd タイマーで15分おきに実行。`state.db` を読み取り専用で読み、`POST /api/v1/conversations` に送る。データの流れは Hermes → API だけで遮断を崩さない）。同じ会話は何度送っても上書きで二重にならず、アプリで始めた会話（チャット画面・パネル）はチャット画面から削除でき（`deleted_conversations` 表に覚え、同期 API は削除済みの会話とその続きを無視する）、Element X の会話は消せない。結び付けの解析（`app/utils/conversation_links.py`）を直したら `uv run flask --app app relink-conversations`。配置と運用は `docs/api/hermes-conversation-sync.md`、設計は `../garden-app-private/docs/superpowers/specs/2026-10-26-hermes-conversations-design.md`

## Hermes のアドバイス

Hermes が相談・質問に答えたら、そのアドバイス（見出し・相談・答えの Markdown）を API（`/api/v1/advices`）で1件ずつ保存する（同じ会話の同じ話題は PATCH で更新、話題が変われば新規、別の会話では常に新規。作業の依頼は保存しない。保存前の確認なし）。作物・品種・植え付けとひも付き、`/advices/`（一覧・詳細・編集・削除。新規作成は Hermes のみ）と、植え付け・品種・作物の詳細画面の「Hermes のアドバイス」の欄（品種・作物は配下の分もまとめて表示）で振り返れる。実装は `app/models/advice.py` + `app/routes/advice_routes.py` + `_hermes_advice_section.html` + `app/api/advices.py`、指示は `hermes-skill/SKILL.md` の「相談・アドバイスの保存」、設計は `../garden-app-private/docs/superpowers/specs/2026-10-27-hermes-advice-design.md`

## ログイン（パスキー）

閲覧は誰でもでき（家族はログイン不要）、登録・編集・削除・アップロード・AI 下書き・見取り図の保存などは、パスキー（PC は Windows Hello、iPhone・iPad は Face ID）でログインした自分だけができる。入口は2つ: `http://<サーバーのIP>:5000` は誰にとっても閲覧専用（セッションの Cookie に `Secure` を付けるので HTTP にはログインが届かない）、`https://<サーバーのホスト名>.local/`（サーバーの avahi の名前＋Caddy の `tls internal`、443番）が編集の入口。実装は `app/auth.py`（`before_request` で **GET・HEAD・OPTIONS 以外はログインが無ければ既定で拒否**、編集用の GET は `OWNER_ONLY_GET_ENDPOINTS` に載せたものだけ `/auth/login` へ案内、CSRF 照合、Jinja グローバル `is_owner()` / `csrf_token()` / `owner_base_url`）+ `app/routes/auth_routes.py`（Blueprint `auth`、`/auth`）+ `app/models/passkey.py`（`passkeys` 表）+ `app/static/js/csrf.js`（フォームの隠し項目と `fetch` のヘッダーに CSRF トークンを自動で付ける）。ログインは 180 日保ち、セッションは「どのパスキーでログインしたか」を持つので、設定画面（`/settings/`）でそのパスキーを消せばその端末のログインはすぐ切れる。依存は `webauthn`（py_webauthn）。**非常口**（最初の1つ目・全部の端末をなくしたとき）はサーバーで `sudo -u garden -H bash -c 'cd /opt/garden-app && ~/.local/bin/uv run flask --app app passkey-register-link'`（開発では `uv run flask --app app passkey-register-link [--base-url URL]`）が出す1回限り・15分の登録用 URL。これが自分だけのものである根拠は、Hermes の実行ユーザーが sudo をパスワード無しで使えない（`NOPASSWD` を足さない、sudo の記憶は端末ごとのまま）ことと、Hermes が 443 番に届かないこと（ufw、`docs/api/migration-to-ubuntu.md` の手順 10）。**これらを崩す変更（`NOPASSWD`、Hermes の遮断を外す、Caddy の転送先を増やす）をしない**。`.env` は `PASSKEY_RP_ID`（開発の既定 `localhost`）、`PASSKEY_ORIGIN`（既定 `http://localhost:5000`）、`OWNER_BASE_URL`（既定は `PASSKEY_ORIGIN`。HTTP の入口からログインを押したときの移動先）、`SESSION_COOKIE_SECURE`（本番の既定は有効、`0` で外す）、固定の `SECRET_KEY`（無いと再起動のたびにログインが外れる）、`WEB_BASE_URL` は本番では HTTPS の URL。開発は `http://localhost:5000`（`127.0.0.1` ではパスキーの RP ID が合わない）で Windows Hello のまま登録・ログインできる。iPhone・iPad は「セキュリティ Wi-Fi」の SSID で `.local` を引けないので、編集は 5G の SSID で行う（2026-10-28 からふだんの接続先を 5G にした）（閲覧は IP の HTTP で今までどおり）。設計は `../garden-app-private/docs/superpowers/specs/2026-10-28-owner-login-passkey-design.md`

## 外部API（エージェント連携）

`/api/v1/*` の JSON API で作物・品種・場所・植え付け・栽培記録・収穫・料理・日記・タスク・アドバイス・写真プールを参照・作成・部分更新できる（削除なし）。補足情報は画像（`extra_images`）と URL（`extra_urls`、OGP はインターネット上のアドレスにだけ取りに行く）と YouTube（`extra_youtube`、保存前に oEmbed で動画の有無を確かめタイトルを取る＝架空の URL 対策）を追加できる（テキストは未対応）。Hermes は作物・品種の登録時と「参考になる情報を集めてきて」で Web ページ・YouTube を補足情報に付ける（`hermes-skill/SKILL.md` の「参考情報の集め方」）。本体画像・写真プールの写真は `GET /{種類}/{id}/image`（`?size=thumb`）でファイルとして取得でき、Hermes はこれで栽培記録の写真から生育状況を診断する。Bearer トークン（`.env` の `API_TOKEN`、32文字以上）必須。`server.py` が Web とは別ポート（`API_PORT`、既定5001）で API 専用アプリ `create_api_app()` を起動し、エージェントからは画面の URL に届かないようにしている（`run.py` では起動しない）。実装は `app/api/`（`Resource` 基底クラス＋リソースごとの定義）。仕様は `docs/api/README.md`、エージェント用スキルは `docs/api/hermes-skill/SKILL.md`、Ubuntu への移設手順は `docs/api/migration-to-ubuntu.md`。ネットワーク・画像まわりを変えるときは API 側（`app/api/images.py`）も確認する。サーバーの Hermes は Web 画面（5000番）と `/opt/garden-app`（`uploads/` を含む）に触れない（ufw と権限で遮断。`docs/api/migration-to-ubuntu.md`）ので、Hermes にさせる機能は API だけで完結させる（API が返す `image_url` も Hermes からは開けないので、画像は `/image` エンドポイントで渡す）。アプリがサーバーから外へ接続する処理（OGP 取得など）を API から使うときは、その遮断の抜け道にならないようにする（例: `fetch_ogp(public_only=True)`）。スマホから Hermes へは LAN 内の Matrix（Tuwunel＋Caddy＋Element X、2026-10-18 構築、2026-10-24 から暗号化（E2EE）ありの部屋。`docs/api/hermes-local-chat.md`）で依頼する（Telegram は 2026-10-23 に停止。`../garden-app-private/docs/api/hermes-telegram.md`）。Hermes のモデルは 2026-10-24 から ChatGPT Plus の枠（`openai-codex` の `gpt-6-luna`）で、失敗したときだけ OpenRouter の Haiku に切り替わる（`../garden-app-private/docs/api/hermes-model.md`）。サーバーに常駐するソフトを足すときは、Hermes の実行ユーザーがそれを経由して遮断をすり抜けられないかを確かめる（例: Caddy の管理用 API は `admin off`）
