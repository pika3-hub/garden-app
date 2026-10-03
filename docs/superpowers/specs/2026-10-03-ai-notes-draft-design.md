# 作物・品種メモのAI下書き機能 設計書

- 作成日: 2026-10-03
- ステータス: レビュー待ち

## 1. 背景と目的

作物（`crops.notes`）・品種（`varieties.notes`）のメモ欄は、登録時に入力する余裕がなく空欄のことがほとんど。Claude API を使って栽培情報の下書きを生成し、ユーザーが確認・編集したうえで保存できるようにする。

### 要件（ユーザー確認済み）

- アプリから Claude API を直接呼ぶ（APIキーは新規発行予定）
- 下書きに含める内容:
  1. 植え付け時期・収穫時期・特性（既存の見出し）
  2. 栽培のコツ（株間・水やり・肥料・病害虫・コンパニオンプランツ）
  3. 品種の場合は品種固有の特徴を重視
  4. ユーザーの地域・栽培環境に合わせた時期
- 地域・栽培環境は一度設定すれば固定で使い回す（設定画面で入力、DB保存）
- APIキーは `.env` で管理（DBには保存しない）
- 生成結果はモーダルで確認し「置き換える / 末尾に追記する / 破棄」を選ぶ。DB保存は従来通りフォームの「保存」ボタン押下時のみ
- 作物・品種の新規登録フォームと編集フォームの両方で使える
- 品種の場合は親作物の名前・種類も AI に渡す
- 「Webで調べる」を選択可能（初期値: 品種=ON、作物=OFF）

### 前提

- 個人のローカル運用（waitress 起動、認証・CSRF対策なし）
- AI の出力は誤りを含みうるため、あくまで「ユーザーが確認する下書き」と位置づける

### スコープ外

- 既存の空欄メモを一括で埋めるバッチ処理
- メモの Markdown 描画（現状は詳細画面でもプレーンテキスト表示のため、それに合わせる）
- 作物・品種以外のエンティティ（場所・日記など）への展開

## 2. 全体構成

### 新規ファイル

| ファイル | 役割 |
|---|---|
| `app/utils/ai_notes.py` | Claude API を呼び Markdown 下書きを返す。Flask 非依存の純粋関数 `generate_notes(...)` として実装し単体テスト可能にする |
| `app/models/app_settings.py` | `AppSettings.get(key, default=None)` / `AppSettings.set(key, value)` のキーバリュー設定 |
| `app/migrations/020_add_app_settings.sql` | `app_settings` テーブル作成 |
| `app/routes/settings_routes.py` | Blueprint `settings`。設定画面と下書き生成 API |
| `app/templates/settings/index.html` | 設定画面 |
| `app/templates/_ai_notes_modal.html` | 下書きモーダル（作物・品種フォームから include） |
| `app/static/js/ai-notes.js` | モーダル制御・fetch 呼び出し・テキストエリア反映 |
| `tests/test_ai_notes.py` | `ai_notes.py` の API 非依存部分の pytest |

### 変更ファイル

- `run.py` / `server.py`: `load_dotenv()` 追加（`python-dotenv` は依存済みだが未使用）
- `app/__init__.py`: `settings` Blueprint 登録、テンプレートから APIキー有無を参照できるよう context processor で `ai_available`（bool）を提供
- `app/templates/base.html`: ナビバー右端に歯車アイコン付き「設定」リンク
- `app/templates/crops/form.html` / `app/templates/varieties/form.html`: メモ欄ラベル横に「✨ AIで下書き」ボタン、モーダル include、`ai-notes.js` 読み込み
- `pyproject.toml`: `anthropic` 追加、dev 依存に `pytest` 追加
- ドキュメント（CLAUDE.md のチェックリストに従う）: `app/models/CLAUDE.md`（`app_settings` テーブル）、`app/routes/CLAUDE.md`（URL設計表）、ルート `CLAUDE.md`（機能概要）、`app/templates/CLAUDE.md` / `docs/frontend/` の該当トピック、`README.md`（機能説明と `.env` 設定手順）

## 3. データモデル

```sql
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- 使用キー: `region`（地域・栽培環境の自由記述）
- `AppSettings.set` は `INSERT ... ON CONFLICT(key) DO UPDATE` で upsert し `updated_at` を更新
- `schema.sql` にも同定義を追加（新規DB作成時用）

## 4. URL設計

| エンドポイント | URL | 内容 |
|---|---|---|
| `settings.index` | GET `/settings/` | 設定画面 |
| `settings.update` | POST `/settings/` | 設定保存 → フラッシュメッセージ付きで `settings.index` へリダイレクト |
| `settings.ai_notes_draft` | POST `/settings/ai/notes-draft` | 下書き生成（JSON） |

下書き生成を作物・品種の各 Blueprint でなく `settings` 配下に置くのは、両フォームから共通利用する単一エンドポイントにするため。

### 下書き生成 API

リクエスト（JSON）:
```json
{
  "crop_name": "トマト",
  "crop_type": "果菜類",
  "variety_name": "アイコ",   // 作物フォームからは null
  "use_web_search": true
}
```

- 値はフォームの入力中の値をそのまま送る（未保存の新規登録でも使えるようにするため）
- 品種フォームでは選択中の親作物の名前・種類を送る（親作物の名前・種類はフォームのデータ属性から取得）

レスポンス:
```json
{"ok": true, "markdown": "## 植え付け時期\n..."}
{"ok": false, "error": "APIキーが無効です。.env を確認してください"}
```

サーバー側バリデーション:
- `crop_name` 必須（品種の場合は `variety_name` も必須）→ 欠けていれば 400
- `region` 未設定 → 400 `{"ok": false, "error": "...", "need_settings": true}`
- APIキー未設定 → 400

## 5. AI 呼び出し（`app/utils/ai_notes.py`）

### インターフェース

```python
def generate_notes(crop_name: str, crop_type: str | None, variety_name: str | None,
                   region: str, use_web_search: bool,
                   client: anthropic.Anthropic | None = None) -> str:
    """Markdown の下書きを返す。失敗時は AiNotesError(日本語メッセージ) を送出。"""
```

- `client` を引数で差し替え可能にしてテスト容易性を確保
- `AiNotesError` は利用者向けの日本語メッセージを持つ例外

### リクエスト内容

- モデル: `claude-opus-5-5`
- `output_config={"effort": "medium"}`、`thinking` は省略（adaptive）
- `max_tokens=16000`（非ストリーミング）
- 拒否時の保険: `client.beta.messages.create(..., betas=["server-side-fallback-2026-07-01"], fallbacks="default")`
- Web検索 ON の場合: `tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5, "user_location": {"type": "approximate", "country": "JP"}}]`
- `stop_reason == "pause_turn"` の場合は、返ってきた `content` を assistant メッセージとして追加し再リクエスト（最大3回）
- クライアントのタイムアウト: 180秒

SDK の正確な呼び出し形（beta メソッド・web search ツールの結果ブロック構造・citations の型）は実装時に claude-api スキルの `python/` ドキュメントで確認する。

### プロンプト

システムプロンプト（固定）:
- 役割: 日本の家庭菜園に詳しいアドバイザー
- 出力は後述の見出し構成の Markdown のみ（前置き・後書きなし）
- 時期はユーザーの地域・栽培環境を基準に書く。種まきと苗の植え付けを区別する
- 品種が指定された場合、親作物の一般論ではなく品種固有の特徴（味・サイズ・耐病性・草勢など）を優先する
- 確かでない情報は書かず「情報なし」と明記する
- 参考URLは本文に書かない（コード側で付与するため）

ユーザーメッセージ: 作物名・作物種類・品種名（ある場合）・地域と栽培環境を列挙。

### 出力形式

```markdown
## 植え付け時期
## 収穫時期
## 特性
## 栽培のコツ
- 株間:
- 水やり:
- 肥料:
- 病害虫:
- コンパニオンプランツ:
## 参考URL
- [ページタイトル](https://...)
```

- **「参考URL」はコード側で生成**: レスポンスの text ブロックの citations から URL とタイトルを抽出し、重複を除いて末尾に付与する。AI に URL を書かせないことで、存在しない URL の混入を防ぐ
- Web検索 OFF、または citations が 0 件の場合は「参考URL」セクション自体を出さない

### エラー処理

| 状況 | 利用者向けメッセージ（例） |
|---|---|
| APIキー未設定 | AI機能を使うには .env に ANTHROPIC_API_KEY を設定してください |
| `AuthenticationError` | APIキーが無効です。.env を確認してください |
| `PermissionDeniedError` | APIキーに権限がありません |
| `RateLimitError` | 混み合っています。しばらく待ってから再度お試しください |
| `APITimeoutError` | 時間内に生成が終わりませんでした。もう一度お試しください |
| `APIConnectionError` | 通信エラーです。ネットワーク接続を確認してください |
| `APIStatusError`（5xx） | AIサービス側でエラーが発生しました。時間をおいてお試しください |
| `APIStatusError`（その他） | 生成に失敗しました（詳細: ...） |
| `stop_reason == "refusal"` | この内容は生成できませんでした |
| `stop_reason == "max_tokens"` または pause_turn 上限到達 | 生成が途中で終わりました。もう一度お試しください |

例外は具体的なものから順に捕捉する（`APITimeoutError` は `APIConnectionError` のサブクラスなので先に）。不完全な下書きはモーダルに表示しない。サーバーログには `_request_id` を出力する。

## 6. 画面

### 設定画面（`/settings/`）

- **地域・栽培環境**: テキストエリア（自由記述）。入力例「神奈川県横浜市（温暖地）。露地の畑とベランダのプランター」と、「温暖地・寒冷地などの区分を書くと時期の精度が上がります」の案内
- **AI機能の状態**: `✅ APIキー設定済み` / `⚠️ 未設定` と設定手順（Anthropic Console でキー発行 → `.env` に `ANTHROPIC_API_KEY=...` を追記 → アプリ再起動）。キーそのものは表示しない
- 保存後はフラッシュメッセージ付きで同画面に戻る

### 作物・品種フォーム

**「✨ AIで下書き」ボタン**（メモ欄ラベル横）:
- APIキー未設定（`ai_available` が false）: ボタン無効化＋ツールチップで理由表示、ボタン下に「設定画面で確認」リンク
- それ以外は常に押下可能。押下時に以下をチェック:
  - 作物フォーム: 作物名が空 → 作物名欄に `is-invalid`＋「作物名を入力してください」、フォーカス移動。モーダルは開かない
  - 品種フォーム: 親作物未選択または品種名が空 → 空の欄に同様の表示
  - 地域未設定（サーバーから `need_settings: true`）→ モーダル内に「先に設定画面で地域を登録してください」と設定画面へのリンクを表示

**下書きモーダル**（`_ai_notes_modal.html`）:
1. 「Webで調べる」チェックボックス（初期値: 品種フォーム=ON、作物フォーム=OFF）と目安表示（OFF:「10〜30秒・約5〜10円」/ ON:「30〜90秒・約20〜40円」）
2. 「生成」ボタン押下 → スピナーと経過秒数を表示、生成ボタン無効化（二重送信防止）
3. 結果を編集可能なテキストエリアに表示（詳細画面がプレーンテキスト表示のため描画プレビューは設けない）
4. 「置き換える」「末尾に追記する」「破棄」
   - 追記: 既存メモの末尾に空行を挟んで追加
   - メモ欄が空の場合は「置き換える」を primary ボタンとして強調
5. 反映後もフォームは未保存。DB保存は「保存」ボタン押下時のみ
6. エラー時はモーダル内にアラート表示し、再度「生成」できる

## 7. データフロー

```
フォーム入力値
  → fetch POST (JSON) /settings/ai/notes-draft
  → AppSettings.get('region') を付加
  → ai_notes.generate_notes()
  → Claude API（＋web_search）
  → Markdown ＋ コード生成の参考URL
  → JSON {ok, markdown} / {ok: false, error}
  → モーダルに表示 → ユーザーが反映方法を選択 → テキストエリア
```

## 8. テスト方針

- `tests/test_ai_notes.py`（pytest、実 API は呼ばない）:
  - プロンプト組み立て（作物のみ / 品種あり、地域の埋め込み）
  - Web検索 ON/OFF で `tools` の有無が切り替わること
  - citations からの参考URL生成（重複除去、0件時はセクションなし）
  - `pause_turn` の再リクエストと上限到達時のエラー
  - `stop_reason` が `refusal` / `max_tokens` の場合のエラー
  - SDK 例外 → `AiNotesError` メッセージへの変換
  - いずれもフェイククライアントを `client` 引数で注入
- 実 API の動作確認: APIキー発行後、作物1件・品種1件（Web検索 ON/OFF 各1回）を手動で確認。課金が発生するため自動テストでは呼ばない
- マイグレーション・設定画面の確認: `docs/db-validation-safety.md` に従い `instance/garden.db` をバックアップしてから実施

## 9. コスト見積もり（参考）

Claude Opus 5.5（入力 $4 / 出力 $20 per 1M tokens）での概算:
- Web検索 OFF: 1件あたり約5〜10円
- Web検索 ON: 検索料と検索結果の入力トークンが加わり、1件あたり約20〜40円
