---
name: garden-app
description: 家庭菜園アプリに作物・品種・場所・植え付け・栽培記録・収穫・料理・日記・タスク・写真を登録・更新・検索する。ユーザーが畑の様子、収穫、料理、作業予定、写真を送ってきたときに使う。
---

# 家庭菜園アプリ API

## 接続情報
- ベース URL: 環境変数 `GARDEN_API_URL`（例: `http://127.0.0.1:5001/api/v1`）
- 認証: すべてのリクエストに `Authorization: Bearer $GARDEN_API_TOKEN`
- 呼び出し例: `curl -sS -H "Authorization: Bearer $GARDEN_API_TOKEN" "$GARDEN_API_URL/health"`
- レスポンスは常に `{"ok": true, "data": ...}` か `{"ok": false, "error": {"code", "message", "details"}}`

## 基本の流れ
1. 初回や選択肢が必要なときは `GET /meta` を読む（ステータス・天気・既存の種類やカテゴリ・使える関連キー）
2. 名前から ID を探す: `GET /lookup?q=<名前>`（作物・品種・場所）。植え付けは `GET /plantings?q=<作物名・品種名・場所名>`（既定は栽培中のみ）。表記ゆれ（例: サラダ菜とサラダナ）で0件になることがある。その場合は `/lookup` で作物を探し、`GET /plantings?crop_id=<id>` の結果から品種名で絞る
3. 候補が複数・0件なら、推測で決めずにユーザーに確認する（例: 「ミニトマトの植え付けが2件あります: 南の畑（5/1）とベランダ（5/3）。どちらですか？」）
4. 作成（POST）または更新（PATCH）する
5. 返ってきた `data.web_url` をユーザーに伝える

日本語を含むクエリは `curl -G "$GARDEN_API_URL/lookup" --data-urlencode 'q=ミニトマト'` のように URL エンコードする。

## 依頼の対応表
| ユーザーの依頼 | 呼ぶ API |
|---|---|
| 「アイコに花が咲いた（写真）」 | 植え付けを探す → `POST /planting_records`（`planting_id`, `recorded_at`, `notes`, `image`） |
| 「ミニトマト300g収穫」 | 植え付けを探す → `POST /harvests`（`planting_id`, `harvest_date`, `quantity: 300`, `unit: "g"`、写真があれば `image`） |
| 「トマトサラダを作った」 | `POST /cooking_records`（`title`, `cooked_date`、当日の収穫があれば `relations.harvest_ids`） |
| 「明日追肥する」 | `POST /tasks`（`title`, `due_date` は今日の日付から計算、植え付けが分かれば `relations.planting_ids`） |
| 「今日の畑日記」 | `POST /diary_entries`（`title`, `entry_date`, `content`, `weather`） |
| 「アイコの栽培を終わりにした」 | 植え付けを探す → `POST /plantings/{id}/end` |
| 「ベランダにバジルを植えた」 | `/lookup` で作物・場所を探す → `POST /plantings`（`location_id` と、`crop_id` か `variety_id` の**どちらか一方**） |
| タスクが終わった | `PATCH /tasks/{id}` に `{"status": "completed"}` |
| 登録済みのデータに写真を付けたい | `PATCH /{種類}/{id}` に `-F image=@...`（`data` は省略可）。既存の画像は置き換わるので、ある場合はユーザーに確認し、残すなら `extra_images` で追加する |
| 「新しい品種○○を登録して（写真）」 | `/lookup?q=<作物名>` で作物 ID を探す（作物がなければ先にユーザーに確認）→ `POST /varieties`（`name`, `crop_id`、写真は `image`） |
| 品種のメモ・補足写真 | `PATCH /varieties/{id}` に `{"notes": "..."}`。補足の写真は `-F extra_images=@...`（返却の `extra_images` に `supplement_id` が付く） |
| 写真が複数枚 | 1枚目を `image`、残りを `extra_images`。栽培記録は1件1枚なので、枚数分の記録を作るかユーザーに確認 |
| 写真だけ先に送られた | `POST /photos` でプールに上げ、後で `photo_pool_id` / `extra_photo_pool_ids` で使う |

## 送り方
- JSON: `-H 'Content-Type: application/json' -d '{...}'`
- 写真付き: `-F 'data={...JSON...}' -F image=@/path/to/photo.jpg -F extra_images=@/path/2.jpg`
- 写真を付けられる種類: `image`（本体画像1枚）は作物・品種・場所・栽培記録・収穫・料理・日記。`extra_images`（追加画像）は栽培記録・植え付け以外のすべて（タスクは `extra_images` だけ）。**ユーザーが写真を送ってきたら、依頼された登録に必ず添付する**（付けられるか分からないときは推測で諦めず、そのまま送って 422 の内容を見る）
- 写真のパーツ名: `POST /photos` だけは `-F files=@...`。それ以外は `image` / `extra_images`（パーツ名を間違えると 422）
- multipart の `data` は**ファイルではなく値**。JSON 文字列を `-F "data=$(cat body.json)"` のように渡す（`-F data=@body.json` は 422）
- 省略できる項目は送らない（収穫の `quantity` / `unit`、日記の `weather` など。分からない値を推測で埋めない）
- 日付は `YYYY-MM-DD`。数値に単位を付けない（`"quantity": 300, "unit": "g"`）
- PATCH は変えたい項目だけ送る。`relations` は送ったキーだけ置き換わる（`[]` で全解除、送らないキーはそのまま）
- 品種として植えた植え付けを探すときは、作物 ID で絞り込むと品種経由のものも含まれる（`GET /plantings?crop_id=1`）

## コマンドの実行
- API は `curl` だけで呼ぶ。レスポンスの JSON は**そのまま読んで**、必要な値（ID・名前・日付など）を自分で拾う
- `python3 -c`・`python3 -` などのスクリプトや、`jq` へのパイプで整形・集計しない（実行のたびにユーザーの承認が必要になる）
- レスポンスが長いときは、スクリプトではなく API の条件で絞る（`q`、`crop_id`、`date_from`、`limit` など）
- 一覧は既定で50件まで。件数を答えるときや全件が必要なときは `meta.total` を見て、`data` の件数より多ければ `limit=200` や `offset` で残りも取得する（`data` の件数を総数として答えない）
- ユーザーへの返答は、読んだ内容を自分の言葉でまとめる（表や一覧を作るためにコマンドを使わない）

## 守ること
- **削除はできない**。削除を頼まれたら「API では削除できないので、アプリの画面から操作してください」と伝え、`web_url` を示す
- PATCH の前に、対象（名前・日付・ID）をユーザーに確認する
- 「昨日」「今日」などは、その都度 `date +%F` で今日の日付を確かめて実際の日付に変換し、返答でも日付を明記する（過去の会話や記憶にある日付を使わない）
- 音声入力の文字は誤変換されやすい（品種名が意味の通らない語になるなど）。対象が決まらないときは候補を挙げて確認し、意味の分からない語を登録名に使わない
- 写真から作物・品種を判断するときは、必ず画像を見て確認する（`vision_analyze` など）。画像を見ずに作物名を答えたり登録したりしない。品種名が読み取れなければ、作物名で登録するかユーザーに聞く
- 写真に複数の植え付けが写っていて、対象が一部しか確定しないときは、確定したものから登録し、残りは候補を示して確認する
- 日記などの文章に、店名など確証のない固有名詞を書かない（ユーザーに確認する）
- 422 が返ったら `error.details` の `field` と `reason` を読んで直し、再送は1回まで。直せなければユーザーに内容を伝える
- 接続できない（タイムアウト・接続拒否）ときは再送せず、「菜園アプリのサーバー（メインPC）が起動していない可能性があります」と伝える
- POST がタイムアウトしたときは、同じ内容を再送する前に一覧（例: `GET /harvests?date_from=<今日>`）で登録済みか確認する（二重登録防止）
- 栽培記録・収穫は**栽培中の植え付けにだけ**作成できる（終了済みは 422）。栽培中の植え付けが見つからなければ、終了済みの植え付けを候補に出さず「栽培中の植え付けがありません。先に植え付けを登録しますか？」と伝える
- 415（HEIC など）の場合は、写真を「ファイル」ではなく「写真」として送り直してもらう
- トークンをユーザーへの返答やログに出さない
