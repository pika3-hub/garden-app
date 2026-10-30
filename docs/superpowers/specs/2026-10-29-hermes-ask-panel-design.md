# アプリから Hermes に聞くパネル 設計

2026-10-29 にユーザーと決めた設計。段階5「アプリから Hermes へ依頼を出せるようにする」の作業2（作業1 = パスキーでのログインは PR #94 で本番反映済み。`2026-10-28-owner-login-passkey-design.md`）。

## 目的と背景

ユーザーはアプリを主に **PC** で見ている（スマホは写真のアップロードが中心）。相談したくなるのは PC で画面を見ているときだが、今は「スマホの認証 → Element X → 部屋を選ぶ → 入力欄に触れる → フリック入力」と手数が多い。

相談が生まれやすいのは**植え付けの詳細画面**（今育てている作物の状況が分かるので、状況に応じた質問やアイデアが浮かぶ）。次に**作物・品種の詳細画面**（新しく買った苗や種の栽培方法の相談）。

開いている画面が Hermes に伝わることで、主語や対象を省いた質問ができるようにしたい。例: 玉ねぎの苗の植え付け画面を開きながら「そろそろ植え付けですかね？」。

## 決まったこと（ユーザーが決めた）

- 対象の画面: 植え付けの詳細、作物の詳細、品種の詳細
- 今開いている画面（どのデータか）が Hermes に自動で伝わり、主語を省いた質問ができる
- 相談だけでなく、タスク・日記などの登録も頼める（Element X と同じ）
- 置き方は**右から開くパネル**（モック A）。右下のボタンで開き、画面を見ながら聞ける。スクロールしても消えない
- 会話は**画面（データ）ごとに別**。玉ねぎの植え付けとニンニクの植え付けは別の会話
- 同じ画面を後日開いたら、**過去のやりとりが見えていて、その続きから聞ける**
- パネルでの会話も `/conversations/`（Hermes との会話の一覧）に Element X の会話と並べて出す
- 一覧からの**自由な会話**（PC 版 Element X のようなチャット。対象のデータ無し）はやりたいが、**今回の PR には含めない**（wishlist に記録する）
- **Hermes が使える道具は Element X（Matrix）の経路と同じにする**（絞らない。Claude の提案をユーザーが了承、「まずは」このまま）。理由: Hermes はアプリの API をターミナルの curl で呼んでいるので、ターミナルを外すと API も使えない。wishlist で道具を絞る案があったのは、アプリに認証が無く LAN の誰でも Hermes に頼めてしまう心配からで、パスキーでのログインによって自分だけになった。Hermes の API Server のキーはアプリのサーバーの `.env` にだけ置き、ブラウザには渡さない
- **承認待ち（危険なコマンドなど）は、パネルの中に「許可する／しない」のボタンを出す**（Element X の `!approve` にあたる。Claude の提案をユーザーが了承、「まずは」このまま）
- 上の2つを合わせると「パスキーでログインしたブラウザから、サーバーで任意のコマンドを動かせる」入口が増える（Hermes のソースも API Server のキーについて、推測されうるキーは遠隔からのコード実行になると警告している）。守りの強さが Element X の経路とほぼ同じ（ログイン＋CSRF、キーはサーバーの中だけ、API Server は `127.0.0.1`）であることを前提に認めた。どちらかを後で絞るなら: 承認はパネルに出さず「Element X で承認して」と表示する案、道具は `platform_toolsets.api_server` を変えて curl に代わる API の道具を用意する案（別の作業）

## Claude が決めたこと（ユーザーは確認していない。違えば直す）

- パネルを出すのは**ログイン中だけ**（`is_owner()`）。家族の閲覧（HTTP の入口・未ログイン）には出さない。アプリ側の中継の入口も全部ログイン必須（`app/auth.py` の既定の拒否と CSRF をそのまま使う）
- 「新しく始める」のリンクで、その画面の会話をまっさらからやり直せる（前の会話は一覧に残る）
- パネルの中の過去のやりとりは、同期（15分おき）を待たずに **Hermes から直接読む**（さっきの会話が見えないことを避けるため）。一覧（`/conversations/`）への取り込みは今の同期を広げる
- 答えの途中で別の画面に移っても、Hermes は最後まで続ける（Hermes 側の run はブラウザと切り離されている）。戻ったら答えが見える
- 相談の答えは、今の SKILL.md の決まりどおり「Hermes のアドバイス」に保存され、その画面のアドバイスの欄に並ぶ（この経路でも同じ）
- Hermes が作った・変えた・見たデータは、答えの下にリンクとして出す。履歴を読み直したときも、各回の答えの下に出す（2026-10-29 本番確認でユーザーが決めた）（会話の履歴の結び付けの解析 `app/utils/conversation_links.py` を使える）

## ゴール

1. ログイン中、植え付け・作物・品種の詳細画面の右下に「Hermes に聞く」ボタンがあり、押すと右側にパネルが開く
2. パネルの上に「この植え付け: 玉ねぎ（ネオアース）東の畑」のように、Hermes に伝わる対象が出る
3. 質問を送ると、途中経過（「栽培記録を読んでいます…」など、道具の動き）と答えが届いた順に出る。答えは Markdown として表示する
4. 主語を省いた質問（「そろそろ植え付けですかね？」）に、Hermes がその画面のデータ（API で読む）を踏まえて答える
5. 同じ画面を後日開くと、前のやりとりが日付の区切り付きで見え、続きから聞ける。「新しく始める」でやり直せる
6. 承認待ちになったら、パネルで許可・拒否でき、Hermes が続きを進める
7. パネルでの会話が、同期で `/conversations/` に出る。どの経路（アプリ／Element X）か、どのデータについての会話かが分かり、会話の詳細からそのデータの画面に戻れる

## やらないこと（今回）

- 一覧からの自由な会話（対象のデータが無い会話）。ただし**後から足せる形にしておく**（パネル・中継の仕組みが「対象なし」を扱えるようにする。画面の入口だけ作らない）
- 植え付け・作物・品種以外の画面（場所・栽培記録・収穫・日記・タスク・料理）へのパネル。仕組みは同じなので、要れば後で足す
- パネルからの写真の添付（PC からの相談が中心のため。Hermes の API Server は `data:image/...` を受け付けるので後で足せる）
- Element X の会話をパネルに出すこと（経路が別の会話。Element X の会話は一覧で見る）
- スマホ向けの作り込み（崩れなければよい。主な利用は PC）

## 失敗とみなすこと（動いても不可）

- ログインしていない人（家族・HTTP の入口）が、パネルや中継の入口を通じて Hermes に何かを頼める、または他の人の頼みに承認を返せる
- Hermes の API Server のキーがブラウザに渡る（HTML・JS・応答のどこかに出る）
- Hermes の API Server が LAN に公開される（`127.0.0.1` 以外で待ち受ける）、または Hermes の実行ユーザーがこの仕組みを経由して Web 画面（5000番・443番）や `/opt/garden-app` に届くようになる
- データの流れが「Hermes → アプリ」の向きで新しく増える（同期の API 以外）。今回増えるのは「アプリ → Hermes の API Server」の向きだけ
- 毎回「この植え付けについて」と書かないと、Hermes が対象を取り違える
- パネルの会話が一覧に出ない、または Element X の会話の取り込みが壊れる

## Hermes の API Server について分かっていること（ソースで確認。2026-10-29）

サーバーと同じ版（`73162b00ee`、2026-10-09）の Hermes のソース（GitHub の NousResearch/hermes-agent）を読んだ。公式の説明は `website/docs/user-guide/features/api-server.md`、実装は `gateway/platforms/api_server.py` と `api_server_runs.py`。

- 有効にする: `~/.hermes/.env` に `API_SERVER_ENABLED=true` と `API_SERVER_KEY`。既定で `127.0.0.1:8642` で待ち受ける。gateway（今 Matrix を動かしているもの）と同じプロセスで動く
- `POST /v1/runs`: `input`（文字列）、`instructions`（Hermes のいつもの指示の上に重ねる、その回だけの指示）、`session_id`（同じ値で会話が続く。既存のセッションなら履歴を読み込む）。すぐに `run_id` が返る。`Idempotency-Key` ヘッダーで二重送信を防げる
- `GET /v1/runs/{id}/events`: SSE。`tool.started`（道具の名前と引数の一部）・`tool.completed`・`message.delta`（答えの文字）・`message.interim`・`approval.request`・`run.completed` など。10秒ごとに `: keepalive`
- `GET /v1/runs/{id}`: 状態（`queued` / `running` / `waiting_for_approval` / `completed` / `failed` / `cancelled` / `interrupted`）と `output`
- `POST /v1/runs/{id}/approval`: 承認待ちへの返事。`POST /v1/runs/{id}/stop`: 中断
- `GET /api/sessions/{id}/messages`: セッションの発言（`inline_images=false` で画像を省ける）
- 道具: API Server の既定の道具の組は `hermes-api-server`（ターミナルを含むほぼ全部。Matrix の `hermes-matrix` とほぼ同じ）。`platform_toolsets.api_server` で変えられるが、今回は変えない
- セッションは Hermes の `state.db` に入る。`source` は `api_server` になる見込み（`platform="api_server"`）。今の同期（`tools/hermes_conversation_sync.py`）は `source = 'matrix'` だけを読んでいる
- 同時に動く run は既定で最大10（超えると 429）

## 全体の流れ

```
ブラウザ（パネル、ログイン中）
   │  POST（CSRF 付き）: 質問、対象（種類と ID）
   ▼
アプリ（Flask、garden ユーザー）  … キーは .env の HERMES_API_KEY
   │  POST /v1/runs（instructions に「見ている画面」、session_id）
   ▼
Hermes の API Server（127.0.0.1:8642、Hermes の実行ユーザー）
   │  いつもどおり curl でアプリの API（5001番）を読む・書く
   ▼
アプリの API（Bearer トークン）
```

- 途中経過と答えは、アプリが Hermes の events を中継してブラウザに渡す（中継のやり方は作る人の判断。下の「作る人に任せること」）
- 一覧への取り込みは今の同期（Hermes → `POST /api/v1/conversations`）を広げる

## 「見ている画面」の伝え方

- `instructions` に、対象の種類・ID・表示名と、読むための API を書く。例（文言は作る人が整える）:
  「ユーザーはアプリで植え付け（id=123、玉ねぎ（ネオアース）、東の畑）の画面を見ながら質問している。主語や対象が省かれていたら、この植え付けのことと考える。中身は `GET /plantings/123` と栽培記録で確かめてから答える」
- 中身（栽培記録や写真）はアプリから送らない。Hermes が API で読む（写真は `/image` で見られる。いつもの経路と同じ）
- SKILL.md に「アプリのパネルからの相談」の節を足す（`instructions` の読み方、アドバイスの保存は同じ決まり、答えは短めでよいか等）。SKILL.md はサーバーに送る必要がある（手順は既存のとおり）

## 会話と対象の結び付け（アプリ側）

- アプリに「どの対象の会話が、どの Hermes の `session_id` か」を持つ表を足す（例: `hermes_chats`: 対象の種類・ID（対象なしも許す）、`session_id`、作成・最後の利用時刻、今使っているか）。名前・列は作る人の判断
- `session_id` はアプリが作る（推測されにくい値。例: `garden-<種類>-<ID>-<ランダム>`）。「新しく始める」は新しい `session_id` を作り、前のものを「使っていない」にする
- 対象のデータが消されたら、その会話は一覧には残る（会話の履歴は消さない）。パネルの表は作る人の判断で整理してよい
- 一覧（`conversations`）の会話とこの表を `session_id`（＝ `conversations.hermes_id`）で突き合わせ、「アプリのパネル」「どのデータについて」を表示する。会話の詳細から対象の画面へリンク

## 一覧への取り込み（同期の変更）

- `tools/hermes_conversation_sync.py` が `source = 'api_server'`（実際の値はサーバーで確かめる）の会話も送るようにする。`conversations.source` に入るので、一覧・詳細で経路を出し分けられる
- 同期はサーバーの `~` に置いたスクリプトなので、変えたらサーバーに送り直す（`docs/api/hermes-conversation-sync.md`）
- API Server の他の利用（もしあれば）や Hermes 内部の会話が混ざらないよう、`session_id` の頭（`garden-`）で絞るかは作る人の判断

## 作る人に任せること（判断の目安つき）

- 途中経過の中継のやり方: アプリが Hermes の SSE を受けて、そのままブラウザに SSE で流す（waitress はスレッド10本。同時に使うのは自分だけなので足りる。Caddy は SSE をそのまま通す）か、ブラウザが短い間隔でアプリに問い合わせる形か。目安: SSE の中継。ブラウザが離れても Hermes の run は続くので、戻ったときは `GET /v1/runs/{id}` と会話の発言から組み立て直す
- パネルの見た目（モック A をもとに、既存の Bootstrap 5 とアプリの色に合わせる）。途中経過は道具の名前をそのまま出さず、「植え付けの情報を読んでいます」のように分かる言葉にするか（目安: curl の URL から種類を拾えたら言葉にし、拾えなければ「作業中…」）
- 1つの会話が長くなったときの扱い（Hermes 側の圧縮で `session_id` が変わることがある。`/v1/runs` は古い id でも今の先端を使う。パネルの過去のやりとりの読み方はこれに合わせる）
- 送信中の二重送信の防止（`Idempotency-Key`）、Hermes が止まっているときの表示（「Hermes に届きません」）、タイムアウト
- 承認の返事の値（`once` / `deny` など、ソースで確かめる）

## 先にサーバーで確かめること（計画の最初の段階）

実装の前に、本番のサーバーで次を確かめる（Claude はサーバーを操作できないので、コマンドを示して結果を貼ってもらう）。どれかがだめなら、切り替え先に進むかユーザーに相談する。

| 確かめること | だめだったときの切り替え先 |
|---|---|
| サーバーの Hermes の版（`git -C ~/.hermes/hermes-agent log -1`）。`73162b00ee` から変わっていたら、その版のソースで API Server の部分を読み直す | ― |
| `API_SERVER_ENABLED=true` にして gateway を再起動したあと、Matrix（Element X）が今までどおり動く | API Server を外して元に戻し、相談する |
| `127.0.0.1:8642` で待ち受け、LAN からは届かない（`ss -ltnp`） | 設定で host を明示する |
| garden ユーザーから `127.0.0.1:8642` に届く（`sudo -u garden curl …/health`）。ufw の今のルール（Hermes の実行ユーザーから 5000・443 への拒否）とぶつからない | ルールを足す（Hermes の遮断は崩さない） |
| `POST /v1/runs` に `session_id` と `instructions` を付けて送り、2回目で前の話が続く。`state.db` の `sessions.source` の値 | 続かなければ `conversation_history` を渡す方式を検討 |
| セッションの自動リセット（community プラグイン `hermes-session-reset-policy`、6時間・朝4時）が、この経路の `session_id` にも効くか（効くと「後日の続き」が途切れる） | 効くなら、続きを読めるように履歴を渡す方式か、プラグインの対象外にする設定を探す |
| 危険なコマンドで承認待ちになり、`/approval` で再開できる | パネルでは承認を出さず「Element X で承認して」と表示する、等を相談 |

### 確かめた結果（2026-10-29）

- 版は `73162b00ee` のまま（ソースの読みがそのまま使える）
- `~/.hermes/.env` に `API_SERVER_ENABLED=true` と `API_SERVER_KEY`（43文字）を足して gateway を再起動。`127.0.0.1:8642` だけで待ち受け、Element X も今までどおり返事が来た。控えは `~/.hermes/.env.bak-before-api-server`
- garden ユーザーから `/health` は 200、キー無しの `POST /v1/runs` は 401（ufw の今のルールとぶつからない）
- 同じ `session_id` の2回目で前の話が続いた。`state.db` の `sessions.source` は `api_server`、`parent_session_id` は空
- events の形（`data: <JSON>` の行、`event` で種類）: `tool.started`（`tool`, `preview`）、`tool.completed`（`tool`, `duration`, `error`, `preview`）、`message.delta`（**本文は `delta`**）、`reasoning.available`（`text`）、`approval.request`、`approval.responded`、`run.completed`（`output`, `usage`, `runtime`）。`GET /v1/runs/{id}` は `status`, `output`, `session_id` など
- `GET /api/sessions/{id}/messages?inline_images=false` は `{"object", "session_id", "data": [...], "pagination"}`。各発言は `id`, `role`, `content`, `tool_calls`, `tool_call_id`, `tool_name`, `timestamp`, `display_kind` など
- 承認: `rm -rf` で `approval.request`（`command`, `description`, `request_id`, `choices`: once / session / always / deny）が来て、状態は `waiting_for_approval`。`{"choice": "deny", "request_id": …}` を返すと Hermes は実行せずに答えを返して終わった
- 自動リセット: ソースでは `session_reset` は Matrix などの会話の管理（`SessionStore`）だけが扱い、API Server の run は `session_id` の履歴を `state.db` から直接読む（`_conversation_history_for_session`）ので効かない見込み。実物では、6時間以上あとに同じ `session_id` で続きを聞いて確かめる（確認用の `garden-check-<日付>` の会話を使う）→ **2026-10-30 に確認済み**: `garden-check-2026-10-29` で「昨日覚えた数字は？」に `7です。` と答えた（前日の話が続いた。自動リセットはこの経路に効かない）
- 確認で作った会話（`garden-check-…`）は一覧の取り込みを広げたあと一覧に出る。残してよい（題名で分かる）
- `.env` を変える前に控えを取る（`cp ~/.hermes/.env ~/.hermes/.env.bak-before-api-server`）

## テスト

- アプリ側は Hermes の API Server をフェイクに差し替えてテストする（実物は呼ばない。`tests/conftest.py` の作法）
- ログインしていない／CSRF が無いと、中継の入口がすべて拒否されること（`tests/test_auth*.py` の既存の確かめ方に合わせる）
- キーが HTML・応答に出ないこと
- 対象ごとに別の `session_id`、同じ対象は同じ `session_id`、「新しく始める」で変わること
- `instructions` に対象の種類・ID が入ること
- 同期: `source = 'api_server'` の会話も選ばれ、Element X の会話の選び方は変わらないこと
- 実物での確認は本番（PR のブランチ）で行う（`docs/api/migration-to-ubuntu.md` の「9. 更新の手順」）。メイン PC には Hermes が無いため

## 設定

- アプリの `.env`: `HERMES_API_URL`（既定 `http://127.0.0.1:8642`）、`HERMES_API_KEY`（無ければパネルを出さない、または「設定されていません」を表示）
- Hermes の `~/.hermes/.env`: `API_SERVER_ENABLED=true`、`API_SERVER_KEY`（アプリの `HERMES_API_KEY` と同じ値。32文字以上のランダム）
- 本番の手順は `docs/api/` に文書を足す（例: `hermes-ask-panel.md`。キーの作り方、両方の `.env`、gateway の再起動、確かめ方）

## 文書の更新

- `CLAUDE.md` の主な機能に「Hermes に聞くパネル」を足し、「Hermes との会話の履歴」に経路が2つになったことを書く
- `app/models/CLAUDE.md`（新しい表）、`app/routes/CLAUDE.md`（URL）、`app/templates/CLAUDE.md` または `docs/frontend/*.md`（パネルの部品）
- `docs/api/hermes-conversation-sync.md`（`api_server` の会話も送る）、`docs/api/hermes-skill/SKILL.md`（パネルからの相談）
- `docs/wishlist.md`: この行を「作業2 完了」にし、「一覧からの自由な会話」と「他の画面へのパネル」を新しい行で足す
- `README.md`
