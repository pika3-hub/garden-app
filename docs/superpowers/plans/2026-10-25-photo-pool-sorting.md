# 写真プールの振り分け画面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 写真プールで選んだ写真を1枚ずつ大きく見ながら、作物・品種・場所・植え付け＋栽培記録・栽培記録・収穫・料理・日記として登録し、「保存して次へ」で写真プールに戻らず続けられる画面と、写真ごとの使用先リンクを作る。

**Architecture:** 新しい Blueprint `photo_sort`（`/photo_pool/sort`）がサーバー側で1枚ずつ描画し、フォームを POST → 次の写真へリダイレクトする。状態は URL のパラメーター（`ids` / `pos` / `done`）だけで持つ。AI 下書きは `app/utils/ai_photo_drafts.py`（`ai_notes.py` の呼び出し・エラー処理を共有）を JSON エンドポイント経由で fetch する。使用先リンクは `PhotoPool.get_usage_links()` が一括で解決する。

**Tech Stack:** Flask / Jinja2 / SQLite / Bootstrap 5 / バニラJS / anthropic SDK（structured outputs `output_config.format` + base64 画像）/ pytest

**Spec:** `docs/superpowers/specs/2026-10-25-photo-pool-sorting-design.md`

## Global Constraints

- AI は入力欄に下書きを入れるだけ。保存は必ず人のボタン操作。下書きは「✨ AIで下書き」を押したときだけ（自動で始めない）
- 栽培記録のメモにアドバイスを書かせない（プロンプトに「観察だけ」「写真から分からないことは書かない」）
- 写真は行ごとに `copy_image(src, folder)` で独立したコピーを作り、`PhotoPool.record_usage(photo_id, entity_type, entity_id, copied_path)` を記録する。`entity_type` は既存と同じ `crop` / `variety` / `location` / `planting_record` / `harvest` / `cooking` / `diary`
- モデルは `ai_notes.current_model()`、キー未設定は `ai_notes.is_available()` が偽 → ボタンを出さない。Web 検索は使わない
- 既存の `/photo_pool/<id>/use`、各画面の「写真プールから選択」、`/plantings/bulk/*`・`/harvests/bulk/*` の挙動を変えない
- 振り分け画面では見取り図の配置画面（`plantings.place`）に移らない
- 公開リポジトリ: 文書・コミットに IP・ユーザー名・ローカルパスを書かない
- テストは `tests/conftest.py` の `app` / `client` フィクスチャ（使い捨て DB）。実 API は呼ばない（FakeClient）

## Review Focus

- `ids` に削除済み・存在しない写真 ID が混ざる（別タブで写真を消した後に再読み込み）→ その写真を飛ばして続き、全部無ければ写真プールへ戻る。Task 3 にテスト
- `taken_at` が無い／壊れた文字列の写真 → 日付の初期値は今日、並びは写真プール登録順。Task 3 にテスト
- 使用先が削除済み（作物を消した、補足情報の親を消した）→ リンクにせず「削除済み」、一覧が 500 にならない。Task 1 にテスト
- 栽培記録・収穫で植え付けを1つも選ばずに保存 → エラー表示で同じ写真・入力値を残す。Task 5 にテスト
- AI が JSON の項目を欠いて返す／`stop_reason` が `refusal`・`max_tokens` → `AiNotesError` の日本語メッセージで 502、入力欄は変えない。Task 2 にテスト

---

### Task 1: 写真プールの使用先リンク

**Files:**
- Modify: `app/models/photo_pool.py`（メソッド追加）
- Modify: `app/routes/photo_pool_routes.py`（`index()` で渡す、URL 解決ヘルパー）
- Modify: `app/templates/photo_pool/index.html`（各写真の「n回使用」バッジの下に使用先一覧。折りたたみ等の見せ方は任意）
- Test: `tests/test_photo_pool_usage_links.py`

**Interfaces:**
- Produces: `PhotoPool.get_usage_links(photo_ids: list[int]) -> dict[int, list[dict]]`。各 dict は `{'entity_type', 'entity_id', 'label': str | None, 'target_type': str | None, 'target_id': int | None, 'created_at'}`。`label is None` は使用先が削除済み。`target_*` はリンク先（`supplement` のときは親の `supplements.entity_type` / `entity_id`、それ以外は自分自身）。新しい順。問い合わせは種類ごとにまとめ、写真1枚ごとに SELECT しない
- Produces: `photo_pool_routes.usage_url(link: dict) -> str | None`（`url_for` で `crops.detail(crop_id)` / `varieties.detail(variety_id)` / `locations.detail(location_id)` / `plantings.record_detail(record_id)` / `harvests.detail(harvest_id)` / `cooking.detail(cooking_id)` / `diary.detail(diary_id)` / `tasks.detail(task_id)`。`label is None` なら None）。Task 3 の振り分け画面でも使う

ラベル: 作物=名前、品種=「作物名（品種名）」、場所=名前、栽培記録=「栽培記録 作物名（品種名）記録日」、収穫=「収穫 作物名（品種名）収穫日」、料理=タイトル、日記=タイトル、補足情報=「{親のラベル}の補足情報」。栽培記録・収穫の作物名は `app.models.planting._CV_JOIN` を import して `cv.crop_name, cv.variety` を取る（新しいコピーは作らない）。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_usage_links_resolve_each_type(app): ...
    # 作物・品種・栽培記録・収穫・料理・日記を作り、同じ写真で record_usage
    # assert links[photo_id] の label が上の書式、usage_url が '/crops/1' 等
def test_usage_link_supplement_points_to_parent(app): ...
    # 日記に付けた補足情報 → target_type == 'diary', usage_url == '/diary/{id}'
def test_usage_link_deleted_entity_has_no_url(app): ...
    # 作物を削除 → label is None, usage_url is None
def test_photo_pool_index_shows_links(client): ...
    # GET /photo_pool/ → 200、本文に '/crops/{id}' と「削除済み」
```

- [ ] **Step 2: 実行して失敗を確認** — `uv run pytest tests/test_photo_pool_usage_links.py -v` → `AttributeError: get_usage_links`
- [ ] **Step 3: `get_usage_links` / `usage_url` を実装し、`index()` から `usage_links` をテンプレートに渡して表示**
- [ ] **Step 4: 通ることを確認** — 同コマンド PASS、`uv run pytest` 全体 PASS
- [ ] **Step 5: Commit** — `git commit -m "写真プールに使用先へのリンクを表示"`

---

### Task 2: 写真から AI 下書きを作る関数

**Files:**
- Modify: `app/utils/ai_notes.py`（`generate_notes` の except 連鎖と `stop_reason` 判定を `_request(client, params) -> list` に切り出し、両方から使う。挙動は変えない）
- Create: `app/utils/ai_photo_drafts.py`
- Test: `tests/test_ai_photo_drafts.py`（FakeClient は `tests/test_ai_notes.py` と同じ形をコピー）

**Interfaces:**
- Consumes: `ai_notes.current_model()`, `is_available()`, `AiNotesError`, `NO_API_KEY_MESSAGE`, `MODEL_INFO`, `FALLBACK_BETA`, `_request`
- Produces: `generate_photo_draft(kind: str, image_bytes: bytes, context: dict, client=None, model=None) -> dict[str, str]`
  - `kind` と返すキー: `location` → `{'notes'}`、`planting` / `planting_record` / `harvest` → `{'notes'}`、`cooking` → `{'title', 'category', 'notes'}`、`diary` → `{'title', 'content'}`。それ以外の `kind` は `ValueError`
  - `context`: `planting` / `planting_record` / `harvest` は `{'plantings': [{'label': str, 'previous_notes': str | None}], 'date': 'YYYY-MM-DD'}`、`cooking` は `{'categories': list[str], 'related': list[str]}`、`diary` は `{'related': list[str], 'date'}`、`location` は `{'name': str}`
  - リクエスト: `messages=[{'role': 'user', 'content': [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': ...}}, {'type': 'text', 'text': ...}]}]`、`output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': <kind ごとの object、全キー required、additionalProperties False>}}`、`max_tokens=4000`、`MODEL_INFO[model]['fallbacks']` が真なら `betas=[FALLBACK_BETA]` と `fallbacks='default'`。`tools` は付けない
  - 応答の `text` ブロックを `json.loads` し、全キーが文字列でそろっていなければ `AiNotesError('生成結果を読み取れませんでした。もう一度お試しください')`
- Produces: `PHOTO_SYSTEM_PROMPT`（日本語。家庭菜園の記録係として写真に写った様子だけを書く。アドバイス・推測・写真から分からないこと（収穫量の数など）は書かない。栽培記録・収穫は前回のメモがあれば変化を1〜2文添える。植え付けが複数なら全体で1つのメモ。料理のカテゴリは候補から選び、合わなければ短い新しい名前）

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_planting_record_draft_sends_image_and_previous_notes():
    # FakeClient(response([text_block('{"notes": "第3花房まで開花"}')]))
    # result == {'notes': '第3花房まで開花'}
    # call = client.calls[0]; content[0]['type'] == 'image'
    # '前回' と previous_notes の文字列が text に入る; 'tools' not in call
    # call['output_config']['format']['schema']['required'] == ['notes']
def test_cooking_draft_returns_title_category_notes(): ...
def test_haiku_has_no_fallbacks():  # model='claude-haiku-5-5' → 'fallbacks' not in call
def test_missing_key_in_json_raises():  # '{"title": "x"}' for cooking → AiNotesError
def test_refusal_raises():  # stop_reason='refusal' → AiNotesError
def test_unknown_kind_raises_value_error(): ...
```

- [ ] **Step 2: 実行して失敗を確認** — `uv run pytest tests/test_ai_photo_drafts.py -v` → `ModuleNotFoundError`
- [ ] **Step 3: `_request` の切り出しと `generate_photo_draft` を実装**
- [ ] **Step 4: 通ることを確認** — `uv run pytest tests/test_ai_photo_drafts.py tests/test_ai_notes.py -v` PASS
- [ ] **Step 5: 実 API で1回だけ確かめる（ユーザーの了承を得てから。1回あたり1円未満〜数円）** — スクラッチパッドに書いたスクリプトで、開発 PC の `.env` のキーと `claude-haiku-5-5` で写真プールのサムネイル1枚を `kind='planting_record'` で送り、JSON が返ること・`output_config.format` が受け付けられることを確認。結果を作業記録に残す
- [ ] **Step 6: Commit** — `git commit -m "写真から AI 下書きを作る関数を追加"`

---

### Task 3: 振り分け画面の骨組み（表示・スキップ・終了）

**Files:**
- Create: `app/routes/photo_sort_routes.py`（Blueprint `photo_sort`、`url_prefix='/photo_pool/sort'`）
- Modify: `app/__init__.py`（Blueprint 登録）
- Create: `app/templates/photo_sort/index.html`、`app/static/css/photo_sort.css`（任意）
- Modify: `app/templates/photo_pool/index.html`（選択バーに「選んだ写真を振り分ける」ボタン。選択中の ID を `?ids=` にして遷移）
- Test: `tests/test_photo_sort.py`

**Interfaces:**
- Consumes: `PhotoPool.get_by_id`, `PhotoPool.get_usage_links`, `usage_url`（Task 1）
- Produces:
  - `GET /photo_pool/sort/?ids=3,1,2&pos=0&done=3` → endpoint `photo_sort.index`。`ids` の写真を撮影日時の古い順（`taken_at` が無い・読めないものは `created_at` 順で後ろ）に並べ直してから表示する（並べ直しは最初の表示時に1回。以降の URL は並べ直し済みの `ids`）。存在しない ID は除く。全部無い／`pos` が末尾を超えたら `photo_pool.index` へリダイレクトし `flash(f'{len(done)}枚の写真を登録しました')`
  - `photo_sort_routes.sort_url(ids: list[int], pos: int, done: set[int]) -> str`（Task 4・5 の保存後リダイレクトで使う）
  - `photo_sort_routes.default_date(photo: dict) -> str`（`taken_at` の日付部分、無ければ今日の `YYYY-MM-DD`）
  - 画面: サムネイル列（済＝`done`、現在＝`pos`）、写真を大きく（`data-full` の lightbox 可）、種類の選択（`crop` / `variety` / `location` / `planting` / `planting_record` / `harvest` / `cooking` / `diary`）、選んだ種類の入力欄（Task 4・5 で中身）、「スキップ」（`pos+1` へのリンク）、この写真の使用先一覧（Task 1 のリンク）

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_sort_orders_by_taken_at_and_skips_missing(client): ...
    # taken_at が 10/25, 10/24, None の写真＋存在しない ID 999
    # GET ?ids=a,b,c,999 → 表示される並び b, a, c（ids に 999 が残らない）
def test_skip_moves_to_next_and_finishes(client): ...
    # pos=末尾+1 → 302 で /photo_pool/、flash の件数
def test_default_date_uses_taken_at_or_today(app): ...
def test_photo_pool_index_has_sort_button(client): ...
```

- [ ] **Step 2: 実行して失敗を確認** — `uv run pytest tests/test_photo_sort.py -v` → 404
- [ ] **Step 3: Blueprint・テンプレート・写真プールのボタンを実装**
- [ ] **Step 4: 通ることを確認** — 同コマンド PASS、全体 PASS
- [ ] **Step 5: Commit** — `git commit -m "写真プールの振り分け画面の骨組みを追加"`

---

### Task 4: 1件だけ作る種類の保存（作物・品種・場所・料理・日記）

**Files:**
- Modify: `app/routes/photo_sort_routes.py`（`POST /photo_pool/sort/save`）
- Create: `app/templates/photo_sort/_fields_crop.html`, `_fields_variety.html`, `_fields_location.html`, `_fields_cooking.html`, `_fields_diary.html`
- Test: `tests/test_photo_sort_save.py`

**Interfaces:**
- Consumes: `sort_url`, `default_date`（Task 3）、`Crop.create`, `Variety.create`, `Location.create`, `Cooking.create` + `Cooking.save_relations`, `DiaryEntry.create` + `DiaryEntry.save_relations`, `copy_image`, `PhotoPool.record_usage`
- Produces: `POST /photo_pool/sort/save`（endpoint `photo_sort.save`）。フォームの共通項目: `ids`, `pos`, `done`, `photo_id`, `kind`, `action`（`next` = 次の写真へ、`stay` = 同じ写真のまま種類の選択へ）。成功時は `done` に `photo_id` を足し、`next` なら `pos+1`、`stay` なら同じ `pos` へ `sort_url` でリダイレクト。保存した件を `flash`
  - 種類ごとの項目と必須は既存フォームと同じ名前・同じ検証: 作物（`name`, `crop_type` 必須、`notes`, `icon_path`, `image_color`）、品種（`crop_id`, `name` 必須、`notes`, `icon_path`, `image_color`）、場所（`name` 必須、`location_type`, `notes`。他の列は既存の `locations/form.html` に合わせる）、料理（`title`, `cooked_date` 必須、`category`, `notes`, 関連 `crop_ids` / `variety_ids` / `location_crop_ids` / `harvest_ids`）、日記（`title`, `entry_date` 必須、`content`, `weather`, 関連 `crop_ids` / `variety_ids` / `location_ids` / `location_crop_ids` / `harvest_ids`）
  - 入力エラー時は保存せず、同じ写真の画面を `kind` と入力値を残して描画（200、`flash` danger）
  - 作物・品種のメモ欄には既存の `_ai_notes_button.html` / `_ai_notes_modal.html` / `ai-notes.js` をそのまま置く。アイコン選択は既存フォームと同じ選択肢（`crop_routes._get_crop_icon_list()` を使う）。関連付けは `entity-select-modal.js`

- [ ] **Step 1: 失敗するテストを書く**

```python
@pytest.mark.parametrize('kind, form, table, folder', [...5種...])
def test_save_creates_entity_with_copied_photo(client, kind, form, table, folder): ...
    # 1件でき、image_path が uploads/{folder}/ 配下でプールの元ファイルと別パス、
    # photo_pool_usages に (photo_id, entity_type, id) が1行、
    # 302 の Location が pos=1 & done に photo_id を含む
def test_save_stay_keeps_same_photo(client): ...   # action=stay → pos=0 のまま
def test_save_validation_error_keeps_values(client): ...  # 料理 title 空 → 200、cooked_date の値が残る、件数 0
def test_cooking_relations_saved(client): ...
```

- [ ] **Step 2: 実行して失敗を確認** — `uv run pytest tests/test_photo_sort_save.py -v`
- [ ] **Step 3: 保存処理と入力欄の部品を実装**
- [ ] **Step 4: 通ることを確認** — 同コマンド PASS、全体 PASS
- [ ] **Step 5: Commit** — `git commit -m "振り分け画面で作物・品種・場所・料理・日記を登録"`

---

### Task 5: 植え付けに結び付く種類の保存（植え付け＋栽培記録・栽培記録・収穫）

**Files:**
- Modify: `app/routes/photo_sort_routes.py`（`save` に3種類を追加）
- Create: `app/templates/photo_sort/_fields_planting.html`, `_fields_planting_record.html`, `_fields_harvest.html`
- Test: `tests/test_photo_sort_save.py`（追記）

**Interfaces:**
- Consumes: Task 4 の `save` の流れ、`Planting.plant`, `PlantingRecord.create`, `Harvest.create`, `planting_routes._build_planting_multi_select_data()`（植え付けの複数選択モーダルのデータ。まとめて登録と同じ部品を使う）
- Produces（`kind` ごと）:
  - `planting`: `location_id` と（`crop_id` か `variety_id`）必須、`planted_date`（初期値 `default_date`）、`quantity`, `planting_notes`（植え付けのメモ）、`notes`（栽培記録のメモ）。`Planting.plant` → その ID で `PlantingRecord.create({'location_crop_id', 'recorded_at': planted_date（空なら default_date）, 'notes', 'image_path'})`、使用記録は `planting_record`。`plantings.place` には移らない
  - `planting_record`: `location_crop_id` を複数（`getlist`、1つ以上必須）、`recorded_at` 必須、`notes` は全件共通。植え付けごとに栽培記録1件・写真コピー1つ・使用記録1行
  - `harvest`: `location_crop_id` 複数（1つ以上必須）、`harvest_date` 必須、植え付けごとの `quantity_{lc_id}`（数値でなければエラー）と `unit_{lc_id}`、`notes` は全件共通。植え付けごとに収穫1件・写真コピー1つ・使用記録1行
  - 選べる植え付けは栽培中（`status='active'`）。この画面の途中で作った植え付けも出る

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_planting_creates_planting_and_first_record(client): ...
    # plantings 1件（position_x is None）、planting_records 1件で recorded_at == planted_date、
    # 使用記録 entity_type == 'planting_record'、Location は振り分け画面（/place ではない）
def test_planting_record_multiple_plantings_share_notes(client): ...
    # 2つ選ぶ → 2件、notes 同一、image_path がそれぞれ別ファイル、使用記録 2行
def test_harvest_quantity_per_planting(client): ...
    # quantity_{a}=25 unit_{a}=個, quantity_{b}=3 unit_{b}=本 → 各行の値
def test_harvest_invalid_quantity_keeps_values(client): ...   # 'abc' → 200、件数 0
def test_planting_record_requires_planting(client): ...       # 未選択 → 200、エラー、件数 0
```

- [ ] **Step 2: 実行して失敗を確認** — `uv run pytest tests/test_photo_sort_save.py -v`
- [ ] **Step 3: 実装**
- [ ] **Step 4: 通ることを確認** — 同コマンド PASS、全体 PASS
- [ ] **Step 5: Commit** — `git commit -m "振り分け画面で植え付け・栽培記録・収穫を登録（複数の植え付け対応）"`

---

### Task 6: 「✨ AIで下書き」ボタン

**Files:**
- Modify: `app/routes/photo_sort_routes.py`（`POST /photo_pool/sort/ai-draft`）
- Create: `app/static/js/photo-sort.js`
- Modify: `app/templates/photo_sort/index.html` と Task 4・5 の `_fields_*.html`（場所・植え付け・栽培記録・収穫・料理・日記にボタン。作物・品種は既存の AI メモ下書きのまま）
- Test: `tests/test_photo_sort_ai.py`

**Interfaces:**
- Consumes: `generate_photo_draft`（Task 2）、`PlantingRecord`（前回のメモ）、`Cooking.get_categories()`
- Produces: `POST /photo_pool/sort/ai-draft`（JSON）。リクエスト `{'photo_id', 'kind', 'location_crop_ids': [...], 'date', 'name', 'related': [...]}`。サーバー側で写真プールのサムネイル（`image_path | thumb_path` の実ファイル、無ければ元画像）を読み、`context` を組み立てる。前回のメモ = 植え付けごとに `recorded_at < date` で最新の栽培記録の `notes`（無ければ None）。成功 200 `{'ok': True, 'fields': {...}}`、入力不備 400、キー未設定 400（`NO_API_KEY_MESSAGE`）、生成失敗 502（`{'ok': False, 'error'}`、`settings_routes._draft_error` と同じ形）
  - `photo-sort.js`: ボタンで今の入力（種類・選択中の植え付け・日付・名前・関連）を送り、返った `fields` を対応する入力欄に入れる（既に文字がある欄も上書きし、ボタンの横に「元に戻す」を出して直前の値に戻せるようにする。ダイアログ（`confirm`）は使わない）。処理中はボタンを無効にして経過を表示。`ai_notes.is_available()` が偽ならボタン自体を描画しない

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_ai_draft_passes_previous_notes(client, monkeypatch): ...
    # 植え付けに 10/18 と 10/26 の栽培記録、date=10/25 → context の previous_notes は 10/18 の notes
    # generate_photo_draft を monkeypatch で差し替えて引数を記録
def test_ai_draft_without_key_returns_400(client): ...
def test_ai_draft_error_returns_502(client, monkeypatch): ...   # AiNotesError → 502、error 文言
def test_ai_button_hidden_without_key(client): ...              # 画面に ai-draft ボタンが無い
```

- [ ] **Step 2: 実行して失敗を確認** — `uv run pytest tests/test_photo_sort_ai.py -v`
- [ ] **Step 3: エンドポイントと JS を実装**
- [ ] **Step 4: 通ることを確認** — 同コマンド PASS、全体 PASS
- [ ] **Step 5: ブラウザで確かめる** — `docs/dev-workflow-tips.md` の「コピーDBでのブラウザ確認」に従い、コピー DB で開発サーバーを起動し、写真3枚を選んで栽培記録（植え付け2つ）・収穫・料理を登録、「この写真で続けて登録」、スキップ、最後に写真プールへ戻り使用先リンクから各画面へ移れることを確認。PC 幅とスマホ幅（375px）で崩れないこと。AI 下書きは実キーで1回（ユーザーの了承後）
- [ ] **Step 6: Commit** — `git commit -m "振り分け画面に AI 下書きボタンを追加"`

---

### Task 7: 文書の更新

**Files:**
- Modify: `CLAUDE.md`（主な機能の「写真プール」「AIメモ下書き」に振り分け画面と使用先リンク）、`app/routes/CLAUDE.md`（URL 設計表に `photo_sort`、Blueprint 規約の単数例に `photo_sort_routes.py → photo_sort`）、`docs/frontend/images-and-photo-pool.md`（振り分け画面・使用先リンクの節）、`README.md`、`docs/wishlist.md`（段階4 の行を削除し、「振り分け画面の行き先に補足情報（画像）を足す」を2026-10-25 の行として追加）

- [ ] **Step 1: 各文書を更新**
- [ ] **Step 2: `git status --short` で固有値・余計なファイルが無いことを確認、`uv run pytest` 全体 PASS**
- [ ] **Step 3: Commit** — `git commit -m "振り分け画面の文書を更新"`
