# Hermes のアドバイスの保存と表示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hermes が相談・質問への答えを API でアドバイスとして保存し、植え付け・品種・作物の詳細画面（配下の分を含む）とアドバイスの一覧・詳細・編集画面で振り返れるようにする。

**Architecture:** 新しい表 `advices` ＋ 関連表 `advice_relations`（`task_relations` と同じ形）。モデル `Advice` が「作物・品種・植え付けの範囲」の SQL を1か所で持ち、詳細画面の欄（Jinja グローバル）と API の絞り込みの両方がそれを使う。元の会話とは、既存の会話の取り込み（`conversation_links`）が `/advices` の POST・PATCH を拾うことで自動で結び付く。

**Tech Stack:** Python 3.12 / Flask / SQLite / Jinja2 / Bootstrap 5 / バニラ JS / pytest（`uv run pytest`）

**Spec:** `docs/superpowers/specs/2026-10-27-hermes-advice-design.md`

## Global Constraints

- 文書・コミットに実環境の固有値（IP・ユーザー名・ホスト名・ローカルのパス）を書かない
- 改行コード: 既存ファイルは元の改行を保つ。新規ファイルは LF。Python でファイルを書き換えるときはテキストモード（改行変換）を使わない
- `instance/garden.db` に触れない（テストは `tests/conftest.py` / `tests/api/conftest.py` の使い捨て DB）
- アプリは `PRAGMA foreign_keys` を有効にしていない。ON DELETE CASCADE に頼らず、関連はモデルで消す。アプリ全体の FK 設定は変えない
- マイグレーションは毎回の起動で全ファイルが実行される（`app/database.py` の `run_migrations`）。`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` / `CREATE TRIGGER IF NOT EXISTS` で書く。`schema.sql` は触らない
- `crop_variety_view` との JOIN は `app.models.planting._CV_JOIN` を import して使う（コピーを増やさない）。`cv.*` は使わない
- API は削除なし。アドバイスの保存・更新は Hermes が事前確認せずに行う（SKILL.md で明記）
- UI 文言は日本語。メニュー・見出しの名前は「Hermes のアドバイス」（欄）、「アドバイス」（一覧・タブ）
- 作物名の表記: 品種あり→「品種名（作物名）」、品種なし→「作物名」（既存の `crop_display_name` / `_crop_label` に合わせる）

## Review Focus

1. 品種 V の植え付けに付いたアドバイスは、V の画面と親作物 C の画面に出て、別の作物の画面には出ない。同じアドバイスが V と V の植え付けの両方に付いていても1件だけ出る → Task 1 の `test_scope_*`
2. 品種を削除したとき、その品種に付いたアドバイスは親作物への関連に変わる。すでに親作物にも付いていれば関連は重複しない → Task 1 の `test_variety_delete_promotes_relation*`
3. 植え付けを削除した後も、アドバイスは一覧に残る。詳細・編集画面は消えた関連を出さずに開ける → Task 1 の `test_orphan_relation_hidden`、Task 3 の `test_edit_after_planting_deleted`
4. 栽培終了の植え付けに付いたアドバイスを画面で編集・保存しても、その関連が消えない（編集モーダルに栽培中だけでなく終了済みの植え付けも出す） → Task 3 の `test_edit_keeps_ended_planting_relation`
5. API の PATCH で `answer` だけ送ったとき、関連と `advised_on` はそのまま。POST で `advised_on` を省くと JST の今日になる → Task 2 の `test_patch_answer_only_keeps_others`、`test_create_defaults_advised_on_today`

---

### Task 1: 表とモデル（範囲の SQL を含む）

**Files:**
- Create: `app/migrations/024_add_advices.sql`
- Create: `app/models/advice.py`
- Test: `tests/test_advice_model.py`
- Modify: `app/models/CLAUDE.md`（テーブル一覧・定義に `advices` / `advice_relations` / トリガーを追記）

**Interfaces:**
- Produces（`app/models/advice.py` の `class Advice`、すべて `@staticmethod`。行は `dict`）:
  - `get_by_id(advice_id: int) -> dict | None`
  - `create(data: dict) -> int` — `data` のキーは `title`, `question`, `answer`, `advised_on`。`created_at` / `updated_at` は `get_jst_now()`
  - `update(advice_id: int, data: dict) -> None` — 同じキー。`updated_at` を更新
  - `delete(advice_id: int) -> None` — `advice_relations` の行も一緒に消す
  - `get_all() -> list[dict]` / `search(keyword: str) -> list[dict]` — 並びは `advised_on DESC, id DESC`。`search` は `title` / `question` / `answer` の部分一致（`%` `_` を文字として扱う。`app/models/conversation.py` の `_like_escape` と同じやり方）
  - `get_adjacent(advice_id: int) -> tuple[dict | None, dict | None]` — 一覧の並びで前（新しい側）と後ろ。各 dict は `id`, `title`
  - `get_relations(advice_id: int) -> dict` — `{'crops': [...], 'varieties': [...], 'location_crops': [...]}`。各行の列は `Task.get_relations` の同名キーと同じ（`locations` は無い）。参照先と INNER JOIN するので、消えた作物・品種・植え付けへの関連は出ない
  - `save_relations(advice_id: int, relations: dict) -> None` — キーは `crop_ids`, `variety_ids`, `location_crop_ids`（文字列でも int でも可）。全削除→再登録。`commit` する
  - `scope_clause(entity_type: str) -> tuple[str, int]` — `entity_type` は `'crop' | 'variety' | 'planting'`。`advices` の id を返す副問い合わせの SQL と、そこへ渡す同じ ID の個数を返す（例: `('SELECT ... WHERE ar.variety_id = ? UNION SELECT ... WHERE lc.variety_id = ?', 2)`）。不明な種類は `ValueError`
  - `get_for_entity(entity_type: str, entity_id: int) -> list[dict]` — `scope_clause` の範囲のアドバイス（重複なし、`advised_on DESC, id DESC`）。各 dict にアドバイスの列＋ `via_labels: list[str]`（その画面のデータ自身以外の関連の表示。例 `'植え付け: アイコ（トマト） 南の畑'`、`'品種: アイコ（トマト）'`。植え付けの画面では空でよい）

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_advice_model.py`。`app` フィクスチャと `app.app_context()` を使い、作物・品種・場所・植え付けを SQL で作る。`tests/api/test_api_relations.py` の `ids` フィクスチャと同じ作り方。植え付けの表は `plantings`、関連の列は `location_crop_id`）

```python
def test_create_get_update_delete(app): ...
    # create → get_by_id で title/question/answer/advised_on が一致
    # update で answer が変わり updated_at が入る
    # save_relations 後に delete → advices と advice_relations の両方から消える
    #   assert db.execute('SELECT COUNT(*) FROM advice_relations WHERE advice_id=?', (aid,)).fetchone()[0] == 0

def test_scope_planting(app): ...
    # 植え付け P に付けたアドバイスは get_for_entity('planting', P) に出る、別の植え付けには出ない

def test_scope_variety_includes_its_plantings(app): ...
    # 品種 V に直接 → 出る。品種 V で植えた植え付けに付けた → 出る。V と V の植え付けの両方に付けた → 1件
    # 別の品種 W の植え付けに付けた → 出ない

def test_scope_crop_includes_varieties_and_plantings(app): ...
    # 作物 C に直接 / 親が C の品種 / 作物 C で植えた植え付け / 品種経由の植え付け → すべて出る（重複なし）
    # 別の作物 D の品種の植え付け → 出ない

def test_scope_order_and_via_labels(app): ...
    # advised_on の新しい順、同じ日は id の新しい順
    # 作物の画面で、植え付けに付いたアドバイスの via_labels に '植え付け: アイコ（トマト） 南の畑' が入る

def test_search_keyword_matches_title_question_answer(app): ...
    # '追肥' で title / question / answer のどれに入っていても見つかる。'%' は文字として扱う（全件にならない）

def test_variety_delete_promotes_relation(app): ...
    # 品種 V に付いたアドバイス → DELETE FROM varieties WHERE id=V → 関連は relation_type='crop', crop_id=親作物 になる
    # get_for_entity('crop', 親) に出る

def test_variety_delete_promotes_relation_without_duplicate(app): ...
    # 品種 V と親作物 C の両方に付いていた → 品種削除後、C への関連は1行だけ

def test_orphan_relation_hidden(app): ...
    # 植え付けを DELETE FROM plantings で消す → get_relations の location_crops は空、get_all にはアドバイスが残る
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_advice_model.py -v`
Expected: FAIL（`app.models.advice` が無い）

- [ ] **Step 3: マイグレーション `024_add_advices.sql` を書く**

`advices`（`id`, `title VARCHAR(200) NOT NULL`, `question TEXT`, `answer TEXT NOT NULL`, `advised_on DATE NOT NULL`, `created_at` / `updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))`）、`advice_relations`（`id`, `advice_id INTEGER NOT NULL REFERENCES advices(id) ON DELETE CASCADE`, `relation_type VARCHAR(20) NOT NULL`, `crop_id REFERENCES crops(id)`, `variety_id REFERENCES varieties(id)`, `location_crop_id REFERENCES plantings(id)`、それぞれ ON DELETE CASCADE、`created_at`）、索引（`advice_id` / `crop_id` / `variety_id` / `location_crop_id`、`advices(advised_on)`）。

品種削除のトリガー（親作物への付け替え。重複を先に消す）:

```sql
CREATE TRIGGER IF NOT EXISTS trg_promote_variety_advice_relations_before_delete
BEFORE DELETE ON varieties
FOR EACH ROW
BEGIN
    DELETE FROM advice_relations
     WHERE variety_id = OLD.id
       AND advice_id IN (SELECT advice_id FROM advice_relations
                          WHERE relation_type = 'crop' AND crop_id = OLD.crop_id);
    UPDATE advice_relations
       SET relation_type = 'crop', crop_id = OLD.crop_id, variety_id = NULL
     WHERE variety_id = OLD.id;
END;
```

- [ ] **Step 4: `app/models/advice.py` を実装する**

`Task` のモデル（`app/models/task.py`）の書き方に合わせる。`scope_clause` の範囲は spec の「集約のルール」のとおり（作物は `plantings lc {_CV_JOIN}` の `cv.effective_crop_id = ?`、品種は `varieties.crop_id = ?` の品種も含む）。`get_for_entity` は `WHERE a.id IN ({scope})` で引き、`via_labels` は `get_relations` 相当の名前から作る（その画面の種類・ID 自身の関連は除く）。

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run pytest tests/test_advice_model.py tests/test_fresh_db_schema.py -v`
Expected: PASS

- [ ] **Step 6: `app/models/CLAUDE.md` を更新してコミット**

```bash
git add app/migrations/024_add_advices.sql app/models/advice.py tests/test_advice_model.py app/models/CLAUDE.md
git commit -m "アドバイスの表とモデルを追加（作物・品種・植え付けの範囲で取得、品種削除で親作物へ付け替え）"
```

---

### Task 2: API `/api/v1/advices` と会話への結び付け

**Files:**
- Create: `app/api/advices.py`
- Modify: `app/api/__init__.py`（import に `advices` を追加）
- Modify: `app/api/choices.py`（`ADVICE_RELATION_KEYS = ('crop_ids', 'variety_ids', 'planting_ids')`）
- Modify: `app/api/meta.py`（`relation_keys` に `'advices': list(ADVICE_RELATION_KEYS)`）
- Modify: `app/utils/conversation_links.py`（`RESOURCE_TYPES` に `'advices': 'advice'`）
- Modify: `docs/api/README.md`（「アドバイス」の節。「追加 YouTube」の節の書き方に合わせ、項目・絞り込み・例・Hermes が確認なしで保存する前提を書く）
- Test: `tests/api/test_api_advices.py`、`tests/test_conversation_links.py`（1ケース追加）

**Interfaces:**
- Consumes: `Advice`（Task 1）。`Advice.save_relations` のキーは `location_crop_ids`（`RELATION_SPECS['planting_ids'][3]` と一致するので `RelationsMixin` がそのまま使える）。`Advice.scope_clause`
- Produces: `AdviceResource`（`name='advices'`, `label='アドバイス'`, `web_path='/advices/{id}'`, `relation_table='advice_relations'`, `relation_owner='advice_id'`）。`fields`: `title`（str, 必須, max_len=200）、`question`（str）、`answer`（str, 必須）、`advised_on`（date）。`list_from='advices a'`, `list_id='a.id'`, `list_order='a.advised_on DESC, a.id DESC'`, `search_columns=('a.title', 'a.question', 'a.answer')`, `date_column='a.advised_on'`, `extra_list_args=('crop_id', 'variety_id', 'planting_id')`。会話の結び付けの `entity_type` は `'advice'`

- [ ] **Step 1: 失敗するテストを書く**（`tests/api/test_api_advices.py`。`api` / `sql` フィクスチャ）

```python
def test_create_with_relations(api, ids):
    # POST {'title': '2回目の追肥はいつ？', 'question': '...', 'answer': '## 目安\n- 第3花房', 'advised_on': '2026-10-20',
    #       'relations': {'planting_ids': [P]}} → 201
    # data['relations'] == {'crop_ids': [], 'variety_ids': [], 'planting_ids': [P]}
    # data['web_url'].endswith(f'/advices/{id}')、'extra_images' not in data

def test_create_defaults_advised_on_today(api, monkeypatch):
    # advised_on を省く → JST の今日（app.utils.timezone.get_jst_now()[:10] と一致）

def test_create_requires_title_and_answer(api):
    # title なし / answer なし → 422、errors の field に 'title' / 'answer'

def test_patch_answer_only_keeps_others(api, ids):
    # PATCH {'answer': '更新'} → relations と advised_on と title は変わらない

def test_list_filters_by_scope(api, ids):
    # 品種の植え付けに付けたアドバイスは ?variety_id=V と ?crop_id=C で出る、?crop_id=別の作物 では出ない
    # meta.total がその件数

def test_list_q_and_dates(api):
    # ?q=追肥 は question だけに含むものも返す。?date_from=&date_to= で advised_on を絞る

def test_no_delete(api):
    # DELETE /api/v1/advices/1 → 405
```

`tests/test_conversation_links.py` に追加:

```python
def test_advice_post_and_patch_are_linked():
    # curl -X POST "$GARDEN_API_URL/advices" … とその結果 {"data": {"id": 7}} → ('advice', 7, 'created')
    # curl -X PATCH "$GARDEN_API_URL/advices/7" → ('advice', 7, 'updated')
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/api/test_api_advices.py tests/test_conversation_links.py -v`
Expected: FAIL（404 / 未知の種類）

- [ ] **Step 3: `app/api/advices.py` を実装する**

`app/api/tasks.py` と同じ作り（`RelationsMixin, Resource`、最後に `register(bp, AdviceResource())`）。`to_model` で `advised_on` が空なら `get_jst_now()[:10]`。`list_where` で `crop_id` / `variety_id` / `planting_id` を `Field('int', min_value=1)` で検証し、`a.id IN (<scope_clause の SQL>)` と ID × 個数を足す。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/api tests/test_conversation_links.py -v`
Expected: PASS（既存の API テストも含めて）

- [ ] **Step 5: `docs/api/README.md` を更新してコミット**

```bash
git add app/api/advices.py app/api/__init__.py app/api/choices.py app/api/meta.py app/utils/conversation_links.py docs/api/README.md tests/api/test_api_advices.py tests/test_conversation_links.py
git commit -m "API にアドバイス（/api/v1/advices）を追加し、会話の履歴と結び付ける"
```

---

### Task 3: アドバイスの一覧・詳細・編集・削除の画面

**Files:**
- Create: `app/routes/advice_routes.py`（Blueprint `advices`、`url_prefix='/advices'`）
- Create: `app/templates/advices/list.html`, `detail.html`, `form.html`
- Modify: `app/__init__.py`（Blueprint 登録。`hermes_conversations` に `kinds=None` 引数を足す）
- Modify: `app/templates/base.html`（ナビの「Hermes」を `advices.*` でも active にする）
- Modify: `app/templates/conversations/list.html`（見出しの下に「会話｜アドバイス」の `nav-tabs`。アドバイスの一覧にも同じタブ）
- Modify: `app/models/photo_pool.py`（`_LABEL_QUERIES` に `'advice': ('SELECT id, title FROM advices WHERE id IN ({ph})', lambda r: r['title'])`）
- Modify: `app/routes/photo_pool_routes.py`（`_DETAIL_ENDPOINTS` に `'advice': ('advices.detail', 'advice_id')`）
- Modify: `app/routes/CLAUDE.md`（URL 設計表）
- Test: `tests/test_advice_routes.py`

**Interfaces:**
- Consumes: `Advice`（Task 1）。`task_routes._build_filter_data(crops, varieties, locations, active_plantings)`（import して `locations=[]` で使う）
- Produces: エンドポイント `advices.list`（`/`、`?keyword=`）、`advices.detail`（`/<int:advice_id>`）、`advices.edit`（`/<int:advice_id>/edit`）、`advices.update`（POST `/<int:advice_id>/update`）、`advices.delete`（POST `/<int:advice_id>/delete`）。新規作成のルートは作らない。`hermes_conversations(entity_type, entity_id, kinds=None)` — `kinds` に `('created', 'updated')` を渡すとその区分の会話だけ

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_advice_routes.py`。`client` / `app` フィクスチャ。データは `Advice.create` / `save_relations` で作る）

```python
def test_list_shows_and_searches(client, ...):
    # GET /advices/ に見出しが出る。?keyword=液肥 で answer に液肥を含むものだけ

def test_detail_renders_markdown_and_relations(client, ...):
    # answer '## 目安\n- 第3花房' → '<h2>' を含む。'<script>' は escape される
    # 関連の植え付けの詳細画面へのリンク（/plantings/<id>）が出る

def test_detail_shows_only_created_updated_conversations(client, app, ...):
    # conversation_links に advice の created と、別の会話の viewed を入れる → created の会話だけ出る

def test_update_requires_title_answer_date(client, ...):
    # title 空で POST /advices/<id>/update → 保存されず edit へ redirect

def test_update_saves_fields_and_relations(client, ...):
    # title/question/answer/advised_on/crop_ids/variety_ids/location_crop_ids を送る → 反映

def test_edit_keeps_ended_planting_relation(client, ...):
    # 栽培終了（status='ended'）の植え付けに付いたアドバイスの編集画面に、その植え付けのカード（data-planting-id）が出る

def test_edit_after_planting_deleted(client, ...):
    # 関連の植え付けを DELETE した後も GET /advices/<id> と /edit が 200

def test_delete(client, ...):
    # POST /advices/<id>/delete → 一覧から消え、advice_relations も 0 件

def test_conversation_detail_links_advice(client, ...):
    # 会話の詳細画面で、作った advice へのリンク（/advices/<id>）と見出しが出る
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_advice_routes.py -v`
Expected: FAIL（404）

- [ ] **Step 3: ルートとテンプレートを実装する**

`task_routes.py` と `tasks/*.html` の作りに合わせる。違いだけ:
- 一覧: 日記の一覧（`diary/list.html`）と同じ年・季節・月のバッジフィルター（`date-badge-filter.js`、日付は `advised_on`）とキーワード検索。各行は見出し・日付・関連の名前・本文の冒頭（プレーンテキスト、100字程度）
- 詳細: 見出し・日付・関連（各詳細画面へのリンク）・相談・アドバイス（`|markdown`）・`_detail_nav.html`（`get_adjacent`）・編集／削除ボタン（削除は確認モーダル）・`hermes_conversations('advice', id, kinds=('created', 'updated'))` の欄
- 編集: 見出し・日付（必須）・相談・アドバイス（必須、textarea）・関連（作物・品種・植え付けの3つのモーダル。場所は無し）。植え付けのモーダルには `Planting.get_all_with_stats()` から `status != 'removed'` のもの＋選択済みのものを渡す
- 削除: `Advice.delete` の後 `advices.list` へ

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_advice_routes.py tests/test_conversation_routes.py tests/test_conversation_sections.py tests/test_photo_pool_usage_links.py -v`
Expected: PASS

- [ ] **Step 5: `app/routes/CLAUDE.md` を更新してコミット**

```bash
git add app/routes/advice_routes.py app/templates/advices app/__init__.py app/templates/base.html app/templates/conversations/list.html app/models/photo_pool.py app/routes/photo_pool_routes.py app/routes/CLAUDE.md tests/test_advice_routes.py
git commit -m "アドバイスの一覧・詳細・編集・削除の画面を追加"
```

---

### Task 4: 植え付け・品種・作物の詳細画面の「Hermes のアドバイス」の欄

**Files:**
- Create: `app/templates/_hermes_advice_section.html`
- Create: `app/static/js/advice-section.js`（欄の中の絞り込み）
- Modify: `app/__init__.py`（Jinja グローバル `hermes_advice`）
- Modify: `app/templates/plantings/detail.html`, `app/templates/varieties/detail.html`, `app/templates/crops/detail.html`（`_hermes_conversations_section.html` の include の直前に追加）
- Modify: `docs/frontend/detail-pages.md`（詳細画面の共通部品として、アドバイスの欄と会話の欄の置き方・呼び方を追記）
- Test: `tests/test_advice_sections.py`

**Interfaces:**
- Consumes: `Advice.get_for_entity`（Task 1）、`Conversation.get_by_entity`、`advices.detail` / `conversations.detail`（Task 3）
- Produces: `hermes_advice(entity_type: str, entity_id: int) -> list[dict]` — `Advice.get_for_entity` の各行に `origin_conversation_id: int | None`（`created` の会話の id。無ければ `updated` の会話、どちらも無ければ None）を足したもの。テンプレートの呼び方は会話の欄と同じ: `{% set advice_items = hermes_advice('planting', location_crop.id) %}{% include '_hermes_advice_section.html' %}`

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_advice_sections.py`）

```python
def test_planting_detail_shows_advice_section(client, ...):
    # 植え付けに付いたアドバイス → /plantings/<id> に 'Hermes のアドバイス'、見出し、件数バッジ
    # 欄は会話の欄（id="hermes-conversations"）より前に出る（HTML 内の位置で比べる）

def test_section_hidden_when_empty(client, ...):
    # アドバイスが無い植え付けの画面に 'Hermes のアドバイス' が出ない

def test_variety_and_crop_detail_include_children(client, ...):
    # 品種の植え付けに付いたアドバイスが、品種と親作物の画面に出て、via の印 '植え付け:' が付く

def test_section_links_origin_conversation(client, app, ...):
    # conversation_links に created を入れる → 欄に /conversations/<id> へのリンク。無ければリンクなし
    # 「詳細」リンク /advices/<id>

def test_section_renders_markdown_escaped(client, ...):
    # answer の Markdown は HTML に、生の <script> は escape
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_advice_sections.py -v`
Expected: FAIL

- [ ] **Step 3: 欄を実装する**

spec の「詳細画面の『Hermes のアドバイス』の欄」と見本 A のとおり: カード（見出しに件数バッジ）、絞り込みの入力欄、Bootstrap のアコーディオン（すべて閉じた状態）。閉じた行は見出し・日付・`via_labels` のバッジ。開くと「相談」「アドバイス」（`|markdown`）、「元の会話を見る」（`origin_conversation_id` があるとき）、「詳細」。`advice-section.js` は入力の文字を含まない `.accordion-item` を隠す（見出し・相談・本文のテキストで判定。0件なら「該当なし」を出す）

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest -q`
Expected: 全件 PASS（HEIC の6件はメイン PC では skip）

- [ ] **Step 5: コミット**

```bash
git add app/templates/_hermes_advice_section.html app/static/js/advice-section.js app/__init__.py app/templates/plantings/detail.html app/templates/varieties/detail.html app/templates/crops/detail.html docs/frontend/detail-pages.md tests/test_advice_sections.py
git commit -m "植え付け・品種・作物の詳細画面に Hermes のアドバイスの欄を追加"
```

---

### Task 5: SKILL.md と文書

**Files:**
- Modify: `docs/api/hermes-skill/SKILL.md`
- Modify: `CLAUDE.md`（主な機能に「Hermes のアドバイス」、外部 API の項目に `advices`）、`README.md`（機能説明）
- Modify: `docs/wishlist.md`（「Hermes のアドバイスを植え付けの画面で見られるようにする」の行を削除。「外部 API で補足情報のテキスト…」の行の背景を「アドバイスは専用の表にした。メモしておいての保存先として、先に本番の補足情報テキストの利用実績を調べる」に更新）

- [ ] **Step 1: SKILL.md に「相談・アドバイスの保存」の節を書く**

spec の「Hermes」の節の項目をすべて入れる（保存する／しないとき、同じ会話・同じ話題は `GET /advices/{id}` → `PATCH` で書き足す、話題が変わったら `POST`、別の会話では常に新規、確認なしで保存、`title` / `question` / `answer` / `advised_on`（`date +%F`）の書き方、ひも付けの使い分け、返答の最後に「（アドバイスとして保存しました）」、過去のアドバイスは必要なときだけ読む・その後を毎回聞かない）。curl の例を1つずつ（POST と PATCH）。「よくある依頼」の表に1行、「守ること」の「PATCH の前に確認する」にアドバイスは例外と追記、「生育状況の診断」の最後の行を spec のとおりに改める

- [ ] **Step 2: 確かめる**

Run: `grep -n "advices" docs/api/hermes-skill/SKILL.md docs/api/README.md CLAUDE.md README.md`
Expected: 各ファイルに該当行がある。`git diff` に実環境の固有値が無い

- [ ] **Step 3: コミット**

```bash
git add docs/api/hermes-skill/SKILL.md CLAUDE.md README.md docs/wishlist.md
git commit -m "SKILL.md にアドバイスの保存の指示を追加し、文書を更新"
```

---

### Task 6: 画面の確認（コピー DB）と本番の確認（実装者ではなくメインのセッションが行う）

- [ ] コピー DB（`docs/dev-workflow-tips.md` の手順）で起動し、API で植え付け・品種・作物にアドバイスを数件作って、3つの詳細画面の欄・絞り込み・一覧の検索とバッジ・編集・削除をブラウザで確かめる
- [ ] PR を作り、サーバーを PR のブランチに切り替え、SKILL.md を送って Element X で `/new` → spec の「確かめ方」の本番の5項目を確かめる。反映後に `relink-conversations` を1回
- [ ] ユーザーがマージ → サーバーを main に戻す
