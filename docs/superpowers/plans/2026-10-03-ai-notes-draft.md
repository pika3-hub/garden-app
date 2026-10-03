# 作物・品種メモのAI下書き機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 作物・品種フォームの「✨ AIで下書き」から Claude API でメモの下書き（地域基準の時期・特性・栽培のコツ・任意で参考URL）を生成し、確認のうえフォームへ反映できるようにする。

**Architecture:** Flask 非依存の `app/utils/ai_notes.py` が Claude API 呼び出し（web search・pause_turn 継続・エラー変換・参考URL生成）を担い、`settings` Blueprint が設定画面（地域を `app_settings` テーブルに保存）と JSON の下書き生成エンドポイントを提供する。フロントは共通 include（ボタン＋モーダル）とバニラJS `ai-notes.js` で作物・品種の両フォームに組み込む。

**Tech Stack:** Python 3.12 / Flask 3.1 / SQLite / `anthropic`（Python SDK）/ python-dotenv / Bootstrap 5.3 / バニラJS / pytest

**Spec:** `docs/superpowers/specs/2026-10-03-ai-notes-draft-design.md`

## Global Constraints

- パッケージ管理は uv（`uv add` / `uv run`）。Python は `==3.12.*`
- モデルは `ANTHROPIC_MODEL` で `claude-opus-5-5`（既定）/ `claude-sonnet-5-5` のみ許可。それ以外は警告ログを出して `claude-opus-5-5`
- `output_config={"effort": "medium"}` を常に明示。`thinking` は送らない
- `max_tokens=16000`、非ストリーミング、クライアントタイムアウト 180 秒
- 拒否時の保険: `client.beta.messages.create(..., betas=["server-side-fallback-2026-07-01"], fallbacks="default")`
- Web検索ツール: `{"type": "web_search_20260209", "name": "web_search", "max_uses": 5, "user_location": {"type": "approximate", "country": "JP"}}`
- `pause_turn` の継続は最大 3 回
- APIキーは `.env` の `ANTHROPIC_API_KEY` のみ。DB保存・画面表示しない
- 地域は `app_settings` テーブルのキー `region`
- 参考URLはAIに書かせず、citations からコードで生成
- 自動テストで実 API を呼ばない（課金が発生するため）
- `instance/garden.db` は実データ。テストは必ず tmp_path の DB を使う。手動確認の前に `docs/db-validation-safety.md` に従いバックアップ
- UI 文言は日本語。動的に差し込む文字列は `textContent` で設定（innerHTML 禁止）
- `main.js` は読み込み時に `.alert:not(.alert-permanent)` を自動で閉じて DOM から消すため、モーダル内のアラートには必ず `alert-permanent` を付ける

## Review Focus

1. **空白だけの作物名・品種名** — 空欄と同じ扱いで 400 / フロントで赤枠になること（Task 4 のテスト、Task 5 の手動確認）
2. **品種フォームで送られた `crop_id` が存在しない・数値でない**（別タブで親作物を削除した等）— 500 にならず「親作物が見つかりません」の 400（Task 4 のテスト）
3. **AI の応答にテキストが無い（検索結果ブロックだけ等）／空白のみ** — 空の下書きを出さず「生成結果が空でした」エラー（Task 2 のテスト）
4. **生成中にモーダルを閉じて開き直す・別の生成を始める** — 古いリクエストは中断され、古い応答が新しい表示を上書きしないこと（Task 5 の手動確認手順に含める）
5. **`ANTHROPIC_API_KEY=` のように空文字や空白だけ** — 「未設定」扱い（Task 2 のテスト `is_available`）

---

## File Structure

| ファイル | 種別 | 責務 |
|---|---|---|
| `pyproject.toml` | 変更 | `anthropic` 依存、dev 依存 `pytest`、pytest 設定 |
| `tests/conftest.py` | 新規 | tmp DB を使う Flask app / client フィクスチャ |
| `app/migrations/020_add_app_settings.sql` | 新規 | `app_settings` テーブル |
| `app/schema.sql` | 変更 | 同テーブル定義を追記（新規DB用） |
| `app/models/app_settings.py` | 新規 | `AppSettings.get/set` |
| `tests/test_app_settings.py` | 新規 | AppSettings のテスト |
| `app/utils/ai_notes.py` | 新規 | Claude API 呼び出し一式 |
| `tests/test_ai_notes.py` | 新規 | ai_notes のテスト（フェイククライアント） |
| `app/routes/settings_routes.py` | 新規 | 設定画面・下書き生成 API |
| `app/templates/settings/index.html` | 新規 | 設定画面 |
| `tests/test_settings_routes.py` | 新規 | ルートのテスト |
| `app/__init__.py` | 変更 | Blueprint 登録、context processor |
| `run.py` / `server.py` | 変更 | `load_dotenv()` |
| `app/templates/base.html` | 変更 | ナビバーに「設定」 |
| `app/templates/_ai_notes_button.html` | 新規 | 「✨ AIで下書き」ボタン |
| `app/templates/_ai_notes_modal.html` | 新規 | 下書きモーダル |
| `app/static/js/ai-notes.js` | 新規 | モーダル制御 |
| `app/templates/crops/form.html` / `app/templates/varieties/form.html` | 変更 | ボタン・モーダル・JS の組み込み |
| `docs/frontend/ai-notes.md` | 新規 | フロントのトピックガイド |
| 各 CLAUDE.md / `README.md` | 変更 | ドキュメント更新 |

---

### Task 1: テスト基盤と `app_settings`（テーブル＋モデル）

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `app/migrations/020_add_app_settings.sql`
- Modify: `app/schema.sql`（末尾に追記）
- Create: `app/models/app_settings.py`
- Test: `tests/test_app_settings.py`

**Interfaces:**
- Consumes: `app.create_app(config_name)`, `app.config.config` / `TestingConfig`, `app.database.get_db()`, `app.utils.timezone.get_jst_now()`
- Produces:
  - `AppSettings.get(key: str, default=None) -> str | None`
  - `AppSettings.set(key: str, value: str | None) -> None`
  - pytest フィクスチャ `app`（tmp DB、`ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` を除去済み）と `client`

- [ ] **Step 1: 依存を追加する**

Run:
```bash
uv add anthropic
uv add --dev pytest
```
Expected: `pyproject.toml` の `dependencies` に `anthropic`、`[dependency-groups] dev` に `pytest` が入る。`os error 4551` が出たら Smart App Control が古い `.venv` を止めているので、`.venv` を削除して `uv sync` で作り直す。

続けて SDK の版と HTTP ライブラリを確認する（Task 2 のテストで使う）:
```bash
uv run python -c "import anthropic; print(anthropic.__version__)"
uv run python -c "import importlib.util as u; print('httpx2' if u.find_spec('httpx2') else 'httpx')"
```

- [ ] **Step 2: pytest 設定を `pyproject.toml` に追記する**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: `tests/conftest.py` を作る**

```python
import pytest

from app import create_app
from app.config import config, TestingConfig


@pytest.fixture
def app(tmp_path, monkeypatch):
    """tmp_path 上の使い捨て DB でアプリを生成する（instance/garden.db には触れない）"""
    class PytestConfig(TestingConfig):
        DATABASE = str(tmp_path / 'test.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')

    assert 'garden.db' not in PytestConfig.DATABASE
    monkeypatch.setitem(config, 'pytest', PytestConfig)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_MODEL', raising=False)
    return create_app('pytest')


@pytest.fixture
def client(app):
    return app.test_client()
```

- [ ] **Step 4: 失敗するテストを書く** — `tests/test_app_settings.py`

```python
from app.models.app_settings import AppSettings


def test_get_returns_default_when_missing(app):
    with app.app_context():
        assert AppSettings.get('region') is None
        assert AppSettings.get('region', '') == ''


def test_set_then_get(app):
    with app.app_context():
        AppSettings.set('region', '神奈川県（温暖地）')
        assert AppSettings.get('region') == '神奈川県（温暖地）'


def test_set_overwrites_existing_value(app):
    from app.database import get_db
    with app.app_context():
        AppSettings.set('region', '北海道')
        AppSettings.set('region', '沖縄県')
        assert AppSettings.get('region') == '沖縄県'
        rows = get_db().execute(
            'SELECT COUNT(*) AS n FROM app_settings WHERE key = ?', ('region',)
        ).fetchone()
        assert rows['n'] == 1
```

- [ ] **Step 5: テストが失敗することを確認する**

Run: `uv run pytest tests/test_app_settings.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.models.app_settings'`）

- [ ] **Step 6: マイグレーションとスキーマを書く**

`app/migrations/020_add_app_settings.sql`:
```sql
-- アプリ設定（キーバリュー形式）。region: 地域・栽培環境
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`app/schema.sql` の末尾（`crop_variety_view` 定義の後）に同じ `CREATE TABLE IF NOT EXISTS app_settings (...)` を、コメント `-- アプリ設定（キーバリュー形式）` 付きで追記する。

- [ ] **Step 7: モデルを書く** — `app/models/app_settings.py`

```python
from app.database import get_db
from app.utils.timezone import get_jst_now


class AppSettings:
    """アプリ設定モデル（app_settings テーブル、キーバリュー形式）

    使用キー:
        region: 地域・栽培環境（AIメモ下書きの時期の基準）
    """

    @staticmethod
    def get(key, default=None):
        """設定値を取得（未設定・NULL なら default）"""
        row = get_db().execute(
            'SELECT value FROM app_settings WHERE key = ?', (key,)
        ).fetchone()
        if row is None or row['value'] is None:
            return default
        return row['value']

    @staticmethod
    def set(key, value):
        """設定値を保存（既存キーは上書き）"""
        db = get_db()
        db.execute(
            '''INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value, updated_at = excluded.updated_at''',
            (key, value, get_jst_now())
        )
        db.commit()
```

- [ ] **Step 8: テストが通ることを確認する**

Run: `uv run pytest tests/test_app_settings.py -v`
Expected: 3 passed

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock tests/conftest.py tests/test_app_settings.py app/migrations/020_add_app_settings.sql app/schema.sql app/models/app_settings.py
git commit -m "app_settings テーブルとモデル、pytest 基盤を追加"
```

---

### Task 2: AI 呼び出しモジュール `ai_notes.py`

**Files:**
- Create: `app/utils/ai_notes.py`
- Test: `tests/test_ai_notes.py`

**Interfaces:**
- Consumes: `anthropic` SDK（`anthropic.Anthropic`, 例外クラス群）
- Produces（Task 3〜5 が使う）:
  - `DEFAULT_MODEL: str = 'claude-opus-5-5'`
  - `MODEL_INFO: dict[str, dict]` — キーはモデルID、値は `{'label': str, 'estimate_off': str, 'estimate_on': str}`
  - `NO_API_KEY_MESSAGE: str`
  - `class AiNotesError(Exception)` — `str(e)` が利用者向け日本語メッセージ
  - `resolve_model(env_value: str | None) -> str`
  - `current_model() -> str`
  - `is_available() -> bool`
  - `generate_notes(crop_name: str, crop_type: str | None, variety_name: str | None, region: str, use_web_search: bool, client=None, model: str | None = None) -> str`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_ai_notes.py`

Task 1 Step 1 で確認した HTTP ライブラリに合わせて import が切り替わるようにしてある。

```python
from types import SimpleNamespace

import anthropic
import pytest

try:
    import httpx2 as httpx
except ImportError:  # anthropic 0.x 系
    import httpx

from app.utils import ai_notes
from app.utils.ai_notes import AiNotesError, generate_notes, resolve_model

_REQ = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')


def _status_error(cls, status):
    return cls('error', response=httpx.Response(status, request=_REQ), body=None)


def text_block(text, citations=None):
    return SimpleNamespace(type='text', text=text, citations=citations)


def citation(url, title):
    return SimpleNamespace(type='web_search_result_location', url=url, title=title,
                           cited_text='...')


def response(content, stop_reason='end_turn'):
    return SimpleNamespace(content=content, stop_reason=stop_reason, _request_id='req_test')


class FakeClient:
    """client.beta.messages.create(**kwargs) を記録し、用意した応答を順に返す"""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def call(client, **overrides):
    kwargs = dict(crop_name='ミニトマト', crop_type='トマト', variety_name=None,
                  region='神奈川県（温暖地）露地', use_web_search=False,
                  client=client, model='claude-opus-5-5')
    kwargs.update(overrides)
    return generate_notes(**kwargs)


# --- resolve_model / is_available ---

def test_resolve_model_defaults_when_unset():
    assert resolve_model(None) == 'claude-opus-5-5'
    assert resolve_model('') == 'claude-opus-5-5'


def test_resolve_model_accepts_allowed_values():
    assert resolve_model('claude-sonnet-5-5') == 'claude-sonnet-5-5'
    assert resolve_model(' claude-opus-5-5 ') == 'claude-opus-5-5'


def test_resolve_model_falls_back_on_unknown(caplog):
    assert resolve_model('claude-haiku-4-5') == 'claude-opus-5-5'
    assert 'claude-haiku-4-5' in caplog.text


def test_model_info_covers_allowed_models():
    for model in ('claude-opus-5-5', 'claude-sonnet-5-5'):
        info = ai_notes.MODEL_INFO[model]
        assert info['label'] and info['estimate_off'] and info['estimate_on']


@pytest.mark.parametrize('value, expected', [
    (None, False), ('', False), ('   ', False), ('sk-ant-xxx', True),
])
def test_is_available(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    else:
        monkeypatch.setenv('ANTHROPIC_API_KEY', value)
    assert ai_notes.is_available() is expected


# --- リクエスト内容 ---

def test_request_params_without_web_search():
    client = FakeClient(response([text_block('## 植え付け時期\n4月')]))
    call(client)
    params = client.calls[0]
    assert params['model'] == 'claude-opus-5-5'
    assert params['max_tokens'] == 16000
    assert params['output_config'] == {'effort': 'medium'}
    assert params['betas'] == ['server-side-fallback-2026-07-01']
    assert params['fallbacks'] == 'default'
    assert 'thinking' not in params
    assert 'tools' not in params
    assert '## 栽培のコツ' in params['system']


def test_request_params_with_web_search():
    client = FakeClient(response([text_block('本文')]))
    call(client, use_web_search=True)
    assert client.calls[0]['tools'] == [{
        'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 5,
        'user_location': {'type': 'approximate', 'country': 'JP'},
    }]


def test_user_message_for_crop_contains_crop_and_region():
    client = FakeClient(response([text_block('本文')]))
    call(client)
    message = client.calls[0]['messages'][0]['content']
    assert 'ミニトマト' in message
    assert 'トマト' in message
    assert '神奈川県（温暖地）露地' in message
    assert '品種名' not in message


def test_user_message_for_variety_mentions_variety_specific():
    client = FakeClient(response([text_block('本文')]))
    call(client, crop_name='トマト', crop_type='トマト', variety_name='アイコ')
    message = client.calls[0]['messages'][0]['content']
    assert '品種名: アイコ' in message
    assert '品種固有' in message


def test_uses_given_model():
    client = FakeClient(response([text_block('本文')]))
    call(client, model='claude-sonnet-5-5')
    assert client.calls[0]['model'] == 'claude-sonnet-5-5'


# --- 出力と参考URL ---

def test_returns_joined_text_without_sources_when_search_off():
    client = FakeClient(response([text_block('## 植え付け時期\n'), text_block('4月〜5月')]))
    assert call(client) == '## 植え付け時期\n4月〜5月'


def test_appends_deduplicated_sources_from_citations():
    blocks = [
        SimpleNamespace(type='server_tool_use', id='s1', name='web_search', input={}),
        SimpleNamespace(type='web_search_tool_result', tool_use_id='s1', content=[]),
        text_block('アイコは甘い。', [citation('https://a.example/aiko', 'アイコ | 種苗A')]),
        text_block('裂果しにくい。', [citation('https://a.example/aiko', 'アイコ | 種苗A'),
                                     citation('https://b.example/x', 'B [特集]')]),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result == (
        'アイコは甘い。裂果しにくい。\n\n'
        '## 参考URL\n'
        '- [アイコ | 種苗A](https://a.example/aiko)\n'
        '- [B ［特集］](https://b.example/x)'
    )


def test_no_sources_section_when_search_on_but_no_citations():
    result = call(FakeClient(response([text_block('本文')])), use_web_search=True)
    assert '参考URL' not in result


def test_empty_text_raises():
    blocks = [SimpleNamespace(type='web_search_tool_result', tool_use_id='s1', content=[]),
              text_block('   ')]
    with pytest.raises(AiNotesError, match='空'):
        call(FakeClient(response(blocks)), use_web_search=True)


# --- pause_turn ---

def test_pause_turn_continues_with_accumulated_content():
    first = [SimpleNamespace(type='server_tool_use', id='s1', name='web_search', input={})]
    client = FakeClient(response(first, 'pause_turn'), response([text_block('続き')]))
    assert call(client, use_web_search=True) == '続き'
    second_messages = client.calls[1]['messages']
    assert second_messages[0]['role'] == 'user'
    assert second_messages[1] == {'role': 'assistant', 'content': first}


def test_pause_turn_limit_raises():
    pauses = [response([text_block('途中')], 'pause_turn') for _ in range(4)]
    client = FakeClient(*pauses)
    with pytest.raises(AiNotesError, match='途中'):
        call(client, use_web_search=True)
    assert len(client.calls) == 4  # 初回 + 継続3回


# --- stop_reason ---

def test_refusal_raises():
    with pytest.raises(AiNotesError, match='生成できませんでした'):
        call(FakeClient(response([], 'refusal')))


def test_max_tokens_raises():
    with pytest.raises(AiNotesError, match='途中'):
        call(FakeClient(response([text_block('途中まで')], 'max_tokens')))


# --- 例外変換 ---

@pytest.mark.parametrize('exc, fragment', [
    (lambda: _status_error(anthropic.AuthenticationError, 401), 'APIキーが無効'),
    (lambda: _status_error(anthropic.PermissionDeniedError, 403), '権限'),
    (lambda: _status_error(anthropic.RateLimitError, 429), '混み合って'),
    (lambda: _status_error(anthropic.InternalServerError, 500), 'AIサービス側'),
    (lambda: _status_error(anthropic.BadRequestError, 400), '生成に失敗しました'),
    (lambda: anthropic.APITimeoutError(request=_REQ), '時間内に'),
    (lambda: anthropic.APIConnectionError(request=_REQ), '通信エラー'),
])
def test_sdk_errors_are_translated(exc, fragment):
    with pytest.raises(AiNotesError, match=fragment):
        call(FakeClient(exc()))


def test_missing_api_key_raises_without_client(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(AiNotesError) as e:
        generate_notes('トマト', None, None, '東京', False)
    assert str(e.value) == ai_notes.NO_API_KEY_MESSAGE
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_ai_notes.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.utils.ai_notes'`）

- [ ] **Step 3: 実装する** — `app/utils/ai_notes.py`

```python
"""作物・品種メモの AI 下書き生成（Claude API）

Flask に依存しない。APIキーは環境変数 ANTHROPIC_API_KEY、
モデルは ANTHROPIC_MODEL（許可リストのみ）で指定する。
"""
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'claude-opus-5-5'

# 許可するモデルと、モーダルに表示する目安（1ドル=150円で概算）
MODEL_INFO = {
    'claude-opus-5-5': {
        'label': 'Claude Opus 5.5',
        'estimate_off': '10〜30秒・約10円',
        'estimate_on': '30〜90秒・約35〜40円',
    },
    'claude-sonnet-5-5': {
        'label': 'Claude Sonnet 5.5',
        'estimate_off': '10〜20秒・約5円',
        'estimate_on': '30〜60秒・約20円',
    },
}

MAX_TOKENS = 16000
REQUEST_TIMEOUT_SECONDS = 180.0
MAX_PAUSE_CONTINUATIONS = 3
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
WEB_SEARCH_TOOL = {
    'type': 'web_search_20260209',
    'name': 'web_search',
    'max_uses': 5,
    'user_location': {'type': 'approximate', 'country': 'JP'},
}

NO_API_KEY_MESSAGE = 'AI機能を使うには .env に ANTHROPIC_API_KEY を設定してください'
_MSG_INCOMPLETE = '生成が途中で終わりました。もう一度お試しください'

SYSTEM_PROMPT = """あなたは日本の家庭菜園に詳しいアドバイザーです。
ユーザーが指定した作物（または品種）について、家庭菜園の栽培メモの下書きを作成します。

# 出力ルール
- 次の見出し構成の Markdown だけを出力する。前置き・後書き・挨拶は書かない。
- 時期はユーザーの地域・栽培環境を基準に書く。種まきと苗の植え付けを区別する。
- 品種が指定された場合、親作物の一般論ではなく、その品種固有の特徴（味・サイズ・耐病性・草勢など）を優先して書く。
- 確かでない情報は推測で書かず「情報なし」と書く。
- 参考URLや出典リストは本文に書かない。

# 見出し構成
## 植え付け時期
## 収穫時期
## 特性
## 栽培のコツ
- 株間:
- 水やり:
- 肥料:
- 病害虫:
- コンパニオンプランツ:
"""


class AiNotesError(Exception):
    """利用者向けの日本語メッセージを持つ例外"""


_warned_models = set()


def resolve_model(env_value):
    """ANTHROPIC_MODEL の値を許可リストで検証してモデルIDを返す"""
    value = (env_value or '').strip()
    if not value:
        return DEFAULT_MODEL
    if value in MODEL_INFO:
        return value
    if value not in _warned_models:
        _warned_models.add(value)
        logger.warning('ANTHROPIC_MODEL=%s は未対応のため %s を使用します', value, DEFAULT_MODEL)
    return DEFAULT_MODEL


def current_model():
    """環境変数から現在のモデルIDを返す"""
    return resolve_model(os.environ.get('ANTHROPIC_MODEL'))


def is_available():
    """APIキーが設定されているか（空白のみは未設定扱い）"""
    return bool((os.environ.get('ANTHROPIC_API_KEY') or '').strip())


def _build_user_message(crop_name, crop_type, variety_name, region):
    lines = [f'作物名: {crop_name}']
    if crop_type:
        lines.append(f'作物種類: {crop_type}')
    if variety_name:
        lines.append(f'品種名: {variety_name}')
    lines.append(f'地域・栽培環境: {region}')
    lines.append('')
    if variety_name:
        lines.append(f'「{crop_name}」の品種「{variety_name}」の栽培メモを作成してください。'
                     '品種固有の特徴を優先してください。')
    else:
        lines.append(f'「{crop_name}」の栽培メモを作成してください。')
    return '\n'.join(lines)


def _build_request_params(model, user_message, use_web_search):
    params = {
        'model': model,
        'max_tokens': MAX_TOKENS,
        'system': SYSTEM_PROMPT,
        'output_config': {'effort': 'medium'},
        'betas': [FALLBACK_BETA],
        'fallbacks': 'default',
        'messages': [{'role': 'user', 'content': user_message}],
    }
    if use_web_search:
        params['tools'] = [WEB_SEARCH_TOOL]
    return params


def _extract_text_and_sources(blocks):
    """text ブロックを連結し、citations から (title, url) を重複なしで集める"""
    texts = []
    sources = []
    seen = set()
    for block in blocks:
        if getattr(block, 'type', None) != 'text':
            continue
        texts.append(block.text)
        for cite in getattr(block, 'citations', None) or []:
            url = getattr(cite, 'url', None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append((getattr(cite, 'title', None) or url, url))
    return ''.join(texts).strip(), sources


def _format_sources(sources):
    lines = ['## 参考URL']
    for title, url in sources:
        safe_title = title.replace('[', '［').replace(']', '］')
        lines.append(f'- [{safe_title}]({url})')
    return '\n'.join(lines)


def _call_api(client, params):
    """pause_turn を継続しながら呼び出し、(全 content ブロック, 最終 stop_reason) を返す"""
    user_turn = params['messages'][0]
    blocks = []
    for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
        response = client.beta.messages.create(**params)
        logger.info('AI notes request_id=%s stop_reason=%s',
                    getattr(response, '_request_id', None), response.stop_reason)
        blocks.extend(response.content)
        if response.stop_reason != 'pause_turn':
            return blocks, response.stop_reason
        params = {**params, 'messages': [user_turn, {'role': 'assistant', 'content': list(blocks)}]}
    raise AiNotesError(_MSG_INCOMPLETE)


def generate_notes(crop_name, crop_type, variety_name, region, use_web_search,
                   client=None, model=None):
    """メモの Markdown 下書きを返す。失敗時は AiNotesError を送出する。"""
    model = model or current_model()
    if client is None:
        if not is_available():
            raise AiNotesError(NO_API_KEY_MESSAGE)
        client = anthropic.Anthropic(timeout=REQUEST_TIMEOUT_SECONDS)

    params = _build_request_params(
        model, _build_user_message(crop_name, crop_type, variety_name, region), use_web_search)

    try:
        blocks, stop_reason = _call_api(client, params)
    except anthropic.APITimeoutError:
        raise AiNotesError('時間内に生成が終わりませんでした。もう一度お試しください')
    except anthropic.APIConnectionError:
        raise AiNotesError('通信エラーです。ネットワーク接続を確認してください')
    except anthropic.AuthenticationError:
        raise AiNotesError('APIキーが無効です。.env を確認してください')
    except anthropic.PermissionDeniedError:
        raise AiNotesError('APIキーに権限がありません')
    except anthropic.RateLimitError:
        raise AiNotesError('混み合っています。しばらく待ってから再度お試しください')
    except anthropic.APIStatusError as e:
        logger.error('AI notes API error status=%s request_id=%s message=%s',
                     e.status_code, getattr(e, 'request_id', None), e.message)
        if e.status_code >= 500:
            raise AiNotesError('AIサービス側でエラーが発生しました。時間をおいてお試しください')
        raise AiNotesError(f'生成に失敗しました（詳細: {e.message}）')

    if stop_reason == 'refusal':
        raise AiNotesError('この内容は生成できませんでした')
    if stop_reason == 'max_tokens':
        raise AiNotesError(_MSG_INCOMPLETE)

    text, sources = _extract_text_and_sources(blocks)
    if not text:
        raise AiNotesError('生成結果が空でした。もう一度お試しください')
    if use_web_search and sources:
        return f'{text}\n\n{_format_sources(sources)}'
    return text
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_ai_notes.py -v`
Expected: すべて PASS

例外の生成で失敗する場合（SDK の版で例外コンストラクタの引数が違う）は、`uv run python -c "import anthropic, inspect; print(inspect.signature(anthropic.APIStatusError.__init__)); print(inspect.signature(anthropic.APIConnectionError.__init__))"` で実際のシグネチャを確認し、テストの `_status_error` / ラムダの引数だけを合わせる（実装側は変えない）。

- [ ] **Step 5: SDK が `fallbacks="default"` を受け付けるか確認する**

フェイククライアントでは型を検査しないので、実 SDK の引数定義を確認する:
```bash
uv run python -c "import anthropic, inspect; print('fallbacks' in inspect.signature(anthropic.Anthropic().beta.messages.create).parameters)"
```
（`ANTHROPIC_API_KEY` が無いとクライアント生成で失敗する場合は `ANTHROPIC_API_KEY=dummy` を付けて実行。通信は発生しない）

Expected: `True`。`False` の場合は `_build_request_params` で `'fallbacks': 'default'` を `'extra_body': {'fallbacks': 'default'}` に置き換え、`test_request_params_without_web_search` の該当アサーションを `assert params['extra_body'] == {'fallbacks': 'default'}` に変えてから Step 4 を再実行する。

- [ ] **Step 6: Commit**

```bash
git add app/utils/ai_notes.py tests/test_ai_notes.py
git commit -m "Claude API でメモ下書きを生成する ai_notes モジュールを追加"
```

---

### Task 3: 設定画面（`settings` Blueprint・ナビ・.env 読み込み）

**Files:**
- Create: `app/routes/settings_routes.py`
- Create: `app/templates/settings/index.html`
- Modify: `app/__init__.py`（Blueprint 登録・context processor）
- Modify: `run.py`, `server.py`（`load_dotenv()`）
- Modify: `app/templates/base.html:99-104`（カレンダーの `<li>` の後）
- Test: `tests/test_settings_routes.py`

**Interfaces:**
- Consumes: `AppSettings.get/set`（Task 1）、`ai_notes.is_available()`, `ai_notes.current_model()`, `ai_notes.MODEL_INFO`（Task 2）
- Produces:
  - Blueprint `settings`（`url_prefix='/settings'`）、エンドポイント `settings.index`（GET `/settings/`）、`settings.update`（POST `/settings/`）
  - `REGION_MAX_LENGTH = 500`（`settings_routes` モジュール定数）
  - 全テンプレートで使える `ai_available: bool`, `ai_model: str`, `ai_model_info: dict`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_settings_routes.py`

```python
from app.models.app_settings import AppSettings


def test_settings_page_shows_unconfigured_state(client):
    res = client.get('/settings/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert '地域・栽培環境' in html
    assert '未設定' in html
    assert 'ANTHROPIC_API_KEY' in html
    assert 'Claude Opus 5.5' in html


def test_settings_page_shows_configured_key_without_revealing_it(client, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-secret-value')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-sonnet-5-5')
    html = client.get('/settings/').get_data(as_text=True)
    assert 'APIキー設定済み' in html
    assert 'sk-ant-secret-value' not in html
    assert 'Claude Sonnet 5.5' in html


def test_save_region(client, app):
    res = client.post('/settings/', data={'region': '  神奈川県（温暖地）  '})
    assert res.status_code == 302
    with app.app_context():
        assert AppSettings.get('region') == '神奈川県（温暖地）'
    html = client.get('/settings/').get_data(as_text=True)
    assert '設定を保存しました' in html
    assert '神奈川県（温暖地）' in html


def test_region_too_long_is_rejected(client, app):
    res = client.post('/settings/', data={'region': 'あ' * 501})
    assert res.status_code == 400
    assert '500文字以内' in res.get_data(as_text=True)
    with app.app_context():
        assert AppSettings.get('region') is None


def test_navbar_has_settings_link(client):
    html = client.get('/settings/').get_data(as_text=True)
    assert 'href="/settings/"' in html
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_settings_routes.py -v`
Expected: FAIL（404）

- [ ] **Step 3: ルートを書く** — `app/routes/settings_routes.py`

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.app_settings import AppSettings

bp = Blueprint('settings', __name__, url_prefix='/settings')

REGION_MAX_LENGTH = 500


@bp.route('/', methods=['GET'])
def index():
    """設定画面"""
    return render_template('settings/index.html', region=AppSettings.get('region', ''),
                           region_max_length=REGION_MAX_LENGTH)


@bp.route('/', methods=['POST'])
def update():
    """設定保存"""
    region = (request.form.get('region') or '').strip()
    if len(region) > REGION_MAX_LENGTH:
        flash(f'地域・栽培環境は{REGION_MAX_LENGTH}文字以内で入力してください', 'danger')
        return render_template('settings/index.html', region=region,
                               region_max_length=REGION_MAX_LENGTH), 400
    AppSettings.set('region', region)
    flash('設定を保存しました', 'success')
    return redirect(url_for('settings.index'))
```

400 で再描画する場合は flash がリダイレクト無しで同じレスポンスに出ることを前提にしている（`get_flashed_messages` は同一リクエスト内でも取得できる）。

- [ ] **Step 4: テンプレートを書く** — `app/templates/settings/index.html`

```html
{% extends "base.html" %}

{% block title %}設定 - 家庭菜園管理アプリ{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col">
        <h1><i class="bi bi-gear"></i> 設定</h1>
    </div>
</div>

<div class="row">
    <div class="col-md-8 mx-auto">
        <div class="card mb-4">
            <div class="card-body">
                <h2 class="h5 card-title">地域・栽培環境</h2>
                <form method="POST" action="{{ url_for('settings.update') }}">
                    <div class="mb-3">
                        <label for="region" class="form-label">地域・栽培環境</label>
                        <textarea class="form-control" id="region" name="region" rows="3"
                                  maxlength="{{ region_max_length }}"
                                  placeholder="例: 神奈川県横浜市（温暖地）。露地の畑とベランダのプランター">{{ region }}</textarea>
                        <div class="form-text">
                            AIでメモの下書きを作るとき、植え付け時期・収穫時期の基準になります。
                            温暖地・寒冷地などの区分を書くと時期の精度が上がります。
                        </div>
                    </div>
                    <div class="text-end">
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-check-circle"></i> 保存
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <div class="card">
            <div class="card-body">
                <h2 class="h5 card-title">AI機能の状態</h2>
                {% if ai_available %}
                <p class="mb-2"><i class="bi bi-check-circle-fill text-success"></i> APIキー設定済み</p>
                {% else %}
                <p class="mb-2"><i class="bi bi-exclamation-triangle-fill text-warning"></i> 未設定</p>
                <ol class="small mb-3">
                    <li>Anthropic Console（console.anthropic.com）で API キーを発行します</li>
                    <li>プロジェクト直下の <code>.env</code> に <code>ANTHROPIC_API_KEY=発行したキー</code> を追記します</li>
                    <li>アプリを再起動します</li>
                </ol>
                {% endif %}
                <p class="mb-1">使用中のモデル: <strong>{{ ai_model_info.label }}</strong></p>
                <p class="small text-muted mb-0">
                    <code>.env</code> の <code>ANTHROPIC_MODEL</code> に
                    <code>claude-opus-5-5</code>（品質重視・既定）または
                    <code>claude-sonnet-5-5</code>（コスト・速度重視）を指定して切り替えられます（再起動が必要）。
                </p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Blueprint 登録と context processor を追加する** — `app/__init__.py`

import 群に `settings_routes` を加え、登録を追加:
```python
    from app.routes import (
        crop_routes, variety_routes, location_routes, diary_routes,
        harvest_routes, calendar_routes, task_routes, planting_routes,
        supplement_routes, photo_pool_routes, cooking_routes, settings_routes
    )
    ...
    app.register_blueprint(cooking_routes.bp)
    app.register_blueprint(settings_routes.bp)

    # AI機能の状態をテンプレートへ提供
    @app.context_processor
    def inject_ai_status():
        from app.utils import ai_notes
        model = ai_notes.current_model()
        return {
            'ai_available': ai_notes.is_available(),
            'ai_model': model,
            'ai_model_info': ai_notes.MODEL_INFO[model],
        }
```

- [ ] **Step 6: ナビバーに「設定」を追加する** — `app/templates/base.html`

カレンダーの `</li>`（`</ul>` の直前）の後に追加:
```html
                    <li class="nav-item">
                        {% set is_settings = request.endpoint and request.endpoint.startswith('settings.') %}
                        <a class="nav-link {% if is_settings %}active{% endif %}" href="{{ url_for('settings.index') }}" {% if is_settings %}aria-current="page"{% endif %}>
                            <i class="bi bi-gear"></i> 設定
                        </a>
                    </li>
```

- [ ] **Step 7: `.env` を読み込む** — `run.py` と `server.py`

両ファイルの先頭の import の直後（`create_app` 呼び出しより前、`FLASK_ENV` を読む前）に追加:
```python
from dotenv import load_dotenv

load_dotenv()
```

- [ ] **Step 8: テストが通ることを確認する**

Run: `uv run pytest -v`
Expected: すべて PASS（Task 1・2 のテストを含む）

- [ ] **Step 9: Commit**

```bash
git add app/routes/settings_routes.py app/templates/settings/index.html app/__init__.py app/templates/base.html run.py server.py tests/test_settings_routes.py
git commit -m "設定画面（地域・栽培環境、AI機能の状態）を追加"
```

---

### Task 4: 下書き生成 API（`POST /settings/ai/notes-draft`）

**Files:**
- Modify: `app/routes/settings_routes.py`
- Test: `tests/test_settings_routes.py`（追記）

**Interfaces:**
- Consumes: `AppSettings.get`（Task 1）、`ai_notes.generate_notes`, `ai_notes.is_available`, `ai_notes.AiNotesError`, `ai_notes.NO_API_KEY_MESSAGE`（Task 2）、`Crop.get_by_id(crop_id) -> dict | None`
- Produces: エンドポイント `settings.ai_notes_draft`（POST `/settings/ai/notes-draft`）
  - リクエスト JSON: `{"mode": "crop", "crop_name": str, "crop_type": str, "use_web_search": bool}` または `{"mode": "variety", "crop_id": int|str, "variety_name": str, "use_web_search": bool}`
  - 成功: 200 `{"ok": true, "markdown": str}`
  - 入力不備: 400 `{"ok": false, "error": str}`（地域未設定時は `"need_settings": true` も付く）
  - 生成失敗: 502 `{"ok": false, "error": str}`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_settings_routes.py` に追記

```python
import pytest

from app.models.crop import Crop
from app.utils.ai_notes import AiNotesError

URL = '/settings/ai/notes-draft'


@pytest.fixture
def ready(app, monkeypatch):
    """地域とAPIキーが設定済みの状態にし、generate_notes の呼び出しを記録する"""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    with app.app_context():
        AppSettings.set('region', '神奈川県（温暖地）')
    calls = []

    def fake_generate(crop_name, crop_type, variety_name, region, use_web_search):
        calls.append(dict(crop_name=crop_name, crop_type=crop_type, variety_name=variety_name,
                          region=region, use_web_search=use_web_search))
        return '## 植え付け時期\n4月'

    monkeypatch.setattr('app.routes.settings_routes.generate_notes', fake_generate)
    return calls


def _make_crop(app, name='トマト', crop_type='トマト'):
    with app.app_context():
        return Crop.create({'name': name, 'crop_type': crop_type})


def test_crop_mode_success(client, ready):
    res = client.post(URL, json={'mode': 'crop', 'crop_name': ' ミニトマト ',
                                 'crop_type': 'トマト', 'use_web_search': False})
    assert res.status_code == 200
    assert res.get_json() == {'ok': True, 'markdown': '## 植え付け時期\n4月'}
    assert ready == [dict(crop_name='ミニトマト', crop_type='トマト', variety_name=None,
                          region='神奈川県（温暖地）', use_web_search=False)]


def test_variety_mode_looks_up_parent_crop(client, app, ready):
    crop_id = _make_crop(app, name='ミニトマト', crop_type='トマト')
    res = client.post(URL, json={'mode': 'variety', 'crop_id': str(crop_id),
                                 'variety_name': 'アイコ', 'use_web_search': True})
    assert res.status_code == 200
    assert ready[0] == dict(crop_name='ミニトマト', crop_type='トマト', variety_name='アイコ',
                            region='神奈川県（温暖地）', use_web_search=True)


@pytest.mark.parametrize('payload, fragment', [
    ({'mode': 'crop', 'crop_name': '   '}, '作物名を入力'),
    ({'mode': 'crop'}, '作物名を入力'),
    ({'mode': 'variety', 'crop_id': 99999, 'variety_name': 'アイコ'}, '親作物が見つかりません'),
    ({'mode': 'variety', 'crop_id': 'abc', 'variety_name': 'アイコ'}, '親作物が見つかりません'),
    ({'mode': 'variety', 'variety_name': 'アイコ'}, '親作物が見つかりません'),
    ({'mode': 'unknown', 'crop_name': 'トマト'}, '不正なリクエスト'),
])
def test_invalid_input_returns_400(client, ready, payload, fragment):
    res = client.post(URL, json=payload)
    assert res.status_code == 400
    body = res.get_json()
    assert body['ok'] is False and fragment in body['error']
    assert ready == []


def test_variety_mode_requires_variety_name(client, app, ready):
    crop_id = _make_crop(app)
    res = client.post(URL, json={'mode': 'variety', 'crop_id': crop_id, 'variety_name': ' '})
    assert res.status_code == 400
    assert '品種名を入力' in res.get_json()['error']


def test_non_json_body_returns_400(client, ready):
    res = client.post(URL, data='not json', content_type='text/plain')
    assert res.status_code == 400


def test_missing_region_returns_need_settings(client, app, ready):
    with app.app_context():
        AppSettings.set('region', '')
    res = client.post(URL, json={'mode': 'crop', 'crop_name': 'トマト'})
    assert res.status_code == 400
    body = res.get_json()
    assert body['need_settings'] is True
    assert '地域' in body['error']


def test_missing_api_key_returns_400(client, ready, monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    res = client.post(URL, json={'mode': 'crop', 'crop_name': 'トマト'})
    assert res.status_code == 400
    assert 'ANTHROPIC_API_KEY' in res.get_json()['error']


def test_generation_error_returns_502(client, ready, monkeypatch):
    def failing(*args, **kwargs):
        raise AiNotesError('混み合っています。しばらく待ってから再度お試しください')
    monkeypatch.setattr('app.routes.settings_routes.generate_notes', failing)
    res = client.post(URL, json={'mode': 'crop', 'crop_name': 'トマト'})
    assert res.status_code == 502
    assert res.get_json() == {'ok': False,
                              'error': '混み合っています。しばらく待ってから再度お試しください'}
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_settings_routes.py -v`
Expected: 新規テストが FAIL（404 / `AttributeError: ... has no attribute 'generate_notes'`）

- [ ] **Step 3: 実装する** — `app/routes/settings_routes.py`

import を差し替え:
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.app_settings import AppSettings
from app.models.crop import Crop
from app.utils.ai_notes import AiNotesError, NO_API_KEY_MESSAGE, generate_notes, is_available
```

末尾に追加:
```python
def _draft_error(message, status=400, **extra):
    return jsonify({'ok': False, 'error': message, **extra}), status


def _parse_crop_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@bp.route('/ai/notes-draft', methods=['POST'])
def ai_notes_draft():
    """作物・品種メモの AI 下書きを生成（JSON）"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _draft_error('不正なリクエストです')

    mode = payload.get('mode')
    use_web_search = bool(payload.get('use_web_search'))

    if mode == 'crop':
        crop_name = (payload.get('crop_name') or '').strip()
        crop_type = (payload.get('crop_type') or '').strip() or None
        variety_name = None
        if not crop_name:
            return _draft_error('作物名を入力してください')
    elif mode == 'variety':
        crop_id = _parse_crop_id(payload.get('crop_id'))
        crop = Crop.get_by_id(crop_id) if crop_id is not None else None
        if not crop:
            return _draft_error('親作物が見つかりません。選び直してください')
        crop_name, crop_type = crop['name'], crop['crop_type']
        variety_name = (payload.get('variety_name') or '').strip()
        if not variety_name:
            return _draft_error('品種名を入力してください')
    else:
        return _draft_error('不正なリクエストです')

    region = (AppSettings.get('region') or '').strip()
    if not region:
        return _draft_error('先に設定画面で地域・栽培環境を登録してください', need_settings=True)
    if not is_available():
        return _draft_error(NO_API_KEY_MESSAGE)

    try:
        markdown = generate_notes(crop_name, crop_type, variety_name, region, use_web_search)
    except AiNotesError as e:
        return _draft_error(str(e), status=502)
    return jsonify({'ok': True, 'markdown': markdown})
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest -v`
Expected: すべて PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/settings_routes.py tests/test_settings_routes.py
git commit -m "メモ下書き生成 API を追加"
```

---

### Task 5: フロント（ボタン・モーダル・JS）と作物・品種フォームへの組み込み

**Files:**
- Create: `app/templates/_ai_notes_button.html`
- Create: `app/templates/_ai_notes_modal.html`
- Create: `app/static/js/ai-notes.js`
- Modify: `app/templates/crops/form.html`（メモ欄 72〜75 行目付近、`{% include '_photo_pool_picker_modal.html' %}` の後、`extra_js`）
- Modify: `app/templates/varieties/form.html`（メモ欄 87〜91 行目付近、`{% include '_crop_select_multi_modal.html' %}` の後、`extra_js`）
- Test: `tests/test_settings_routes.py`（描画テストを追記）＋ブラウザでの手動確認

**Interfaces:**
- Consumes: `settings.ai_notes_draft` エンドポイントと JSON 形式（Task 4）、`settings.index`（Task 3）、テンプレート変数 `ai_available`, `ai_model_info`（Task 3）
- Produces: include 部品。呼び出し側は include の前に `{% set ai_mode = 'crop' %}` または `'variety'` を設定する。JS が参照する既存要素 ID: `notes`, `name`, `crop_type`（作物のみ）, `crop_id_hidden` / `selected-crop-display` / `crop-select-error`（品種のみ）

- [ ] **Step 1: 失敗する描画テストを書く** — `tests/test_settings_routes.py` に追記

```python
def test_crop_form_has_ai_button_disabled_without_key(client):
    html = client.get('/crops/new').get_data(as_text=True)
    assert 'id="aiNotesBtn"' in html
    assert 'id="aiNotesModal"' in html
    assert 'data-mode="crop"' in html
    assert 'APIキーが未設定' in html
    assert 'js/ai-notes.js' in html


def test_variety_form_has_ai_button_enabled_with_key(client, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    html = client.get('/varieties/new').get_data(as_text=True)
    assert 'data-mode="variety"' in html
    assert 'APIキーが未設定' not in html
    # 品種は Web検索の初期値 ON
    assert 'id="aiNotesWebSearch" checked' in html
```

Run: `uv run pytest tests/test_settings_routes.py -v -k form`
Expected: FAIL

- [ ] **Step 2: ボタン部品を書く** — `app/templates/_ai_notes_button.html`

```html
{# メモ欄の「AIで下書き」ボタン。include 前に ai_mode ('crop' | 'variety') を set すること #}
{% if ai_available %}
<button type="button" class="btn btn-sm btn-outline-primary" id="aiNotesBtn">
    ✨ AIで下書き
</button>
{% else %}
<span class="text-end">
    <span class="d-inline-block" tabindex="0" data-bs-toggle="tooltip" data-ai-notes-tooltip
          title="APIキーが未設定のため使えません">
        <button type="button" class="btn btn-sm btn-outline-primary" id="aiNotesBtn" disabled>
            ✨ AIで下書き
        </button>
    </span>
    <a href="{{ url_for('settings.index') }}" class="d-block small">APIキーが未設定です（設定画面で確認）</a>
</span>
{% endif %}
```

- [ ] **Step 3: モーダル部品を書く** — `app/templates/_ai_notes_modal.html`

```html
{# メモの AI 下書きモーダル。include 前に ai_mode ('crop' | 'variety') を set すること #}
<div class="modal fade" id="aiNotesModal" tabindex="-1" aria-labelledby="aiNotesModalLabel" aria-hidden="true"
     data-mode="{{ ai_mode }}"
     data-endpoint="{{ url_for('settings.ai_notes_draft') }}"
     data-settings-url="{{ url_for('settings.index') }}">
    <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="aiNotesModalLabel">✨ AIでメモの下書き</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="閉じる"></button>
            </div>
            <div class="modal-body">
                <p class="small text-muted mb-2">
                    対象: <span id="aiNotesTarget"></span> ／ モデル: {{ ai_model_info.label }}
                </p>
                <div class="form-check mb-1">
                    <input class="form-check-input" type="checkbox" id="aiNotesWebSearch"{% if ai_mode == 'variety' %} checked{% endif %}>
                    <label class="form-check-label" for="aiNotesWebSearch">Webで調べる（参考URL付き）</label>
                </div>
                <div class="form-text mb-3" id="aiNotesEstimate"
                     data-estimate-on="目安: {{ ai_model_info.estimate_on }}"
                     data-estimate-off="目安: {{ ai_model_info.estimate_off }}"></div>
                <button type="button" class="btn btn-primary" id="aiNotesGenerateBtn">
                    <i class="bi bi-stars"></i> 生成
                </button>
                <div id="aiNotesProgress" class="mt-3 d-none">
                    <span class="spinner-border spinner-border-sm" role="status"></span>
                    生成中… <span id="aiNotesElapsed">0</span>秒
                </div>
                <div id="aiNotesError" class="alert alert-danger alert-permanent mt-3 mb-0 d-none" role="alert"></div>
                <div id="aiNotesResultWrap" class="mt-3 d-none">
                    <label for="aiNotesResult" class="form-label">
                        下書き（編集できます。AIの情報は誤りを含むことがあるので確認してください）
                    </label>
                    <textarea id="aiNotesResult" class="form-control" rows="14"></textarea>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">破棄</button>
                <button type="button" class="btn btn-outline-success" id="aiNotesAppendBtn" disabled>末尾に追記する</button>
                <button type="button" class="btn btn-outline-success" id="aiNotesReplaceBtn" disabled>置き換える</button>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 4: JS を書く** — `app/static/js/ai-notes.js`

```javascript
/**
 * 作物・品種フォームのメモ AI 下書き（_ai_notes_button.html + _ai_notes_modal.html）
 */
(function () {
    'use strict';

    document.querySelectorAll('[data-ai-notes-tooltip]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    var btn = document.getElementById('aiNotesBtn');
    var modalEl = document.getElementById('aiNotesModal');
    if (!btn || !modalEl || btn.disabled) return;

    var mode = modalEl.dataset.mode;
    var endpoint = modalEl.dataset.endpoint;
    var settingsUrl = modalEl.dataset.settingsUrl;

    var notesEl = document.getElementById('notes');
    var nameEl = document.getElementById('name');
    var cropTypeEl = document.getElementById('crop_type');
    var cropIdEl = document.getElementById('crop_id_hidden');
    var cropDisplayEl = document.getElementById('selected-crop-display');
    var cropErrorEl = document.getElementById('crop-select-error');

    var targetEl = document.getElementById('aiNotesTarget');
    var webSearchEl = document.getElementById('aiNotesWebSearch');
    var estimateEl = document.getElementById('aiNotesEstimate');
    var generateBtn = document.getElementById('aiNotesGenerateBtn');
    var progressEl = document.getElementById('aiNotesProgress');
    var elapsedEl = document.getElementById('aiNotesElapsed');
    var errorEl = document.getElementById('aiNotesError');
    var resultWrap = document.getElementById('aiNotesResultWrap');
    var resultEl = document.getElementById('aiNotesResult');
    var appendBtn = document.getElementById('aiNotesAppendBtn');
    var replaceBtn = document.getElementById('aiNotesReplaceBtn');

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    var controller = null;
    var timerId = null;

    function markInvalid(el) {
        el.classList.add('is-invalid');
        el.focus();
        el.addEventListener('input', function clear() {
            el.classList.remove('is-invalid');
            el.removeEventListener('input', clear);
        });
    }

    function validate() {
        if (mode === 'variety' && !cropIdEl.value) {
            cropErrorEl.style.display = '';
            cropDisplayEl.classList.add('border', 'border-danger');
            cropDisplayEl.scrollIntoView({ block: 'center' });
            return false;
        }
        if (!nameEl.value.trim()) {
            markInvalid(nameEl);
            return false;
        }
        return true;
    }

    function targetLabel() {
        var name = nameEl.value.trim();
        if (mode === 'variety') {
            return name + '（' + cropDisplayEl.textContent.trim() + '）';
        }
        return name;
    }

    function updateEstimate() {
        estimateEl.textContent = webSearchEl.checked
            ? estimateEl.dataset.estimateOn
            : estimateEl.dataset.estimateOff;
    }

    function setApplyEnabled(enabled) {
        appendBtn.disabled = !enabled;
        replaceBtn.disabled = !enabled;
        var notesEmpty = !notesEl.value.trim();
        replaceBtn.classList.toggle('btn-success', enabled && notesEmpty);
        replaceBtn.classList.toggle('btn-outline-success', !(enabled && notesEmpty));
    }

    function hideError() {
        errorEl.classList.add('d-none');
        errorEl.textContent = '';
    }

    function showError(message, needSettings) {
        errorEl.textContent = message;
        if (needSettings) {
            var link = document.createElement('a');
            link.href = settingsUrl;
            link.className = 'alert-link ms-1';
            link.textContent = '設定画面を開く';
            errorEl.appendChild(link);
        }
        errorEl.classList.remove('d-none');
    }

    function startProgress() {
        var started = Date.now();
        elapsedEl.textContent = '0';
        progressEl.classList.remove('d-none');
        generateBtn.disabled = true;
        webSearchEl.disabled = true;
        timerId = setInterval(function () {
            elapsedEl.textContent = String(Math.floor((Date.now() - started) / 1000));
        }, 1000);
    }

    function stopProgress() {
        clearInterval(timerId);
        timerId = null;
        progressEl.classList.add('d-none');
        generateBtn.disabled = false;
        webSearchEl.disabled = false;
    }

    function resetModal() {
        if (controller) controller.abort();
        stopProgress();
        hideError();
        resultEl.value = '';
        resultWrap.classList.add('d-none');
        setApplyEnabled(false);
        webSearchEl.checked = (mode === 'variety');
        updateEstimate();
        targetEl.textContent = targetLabel();
    }

    function buildPayload() {
        var payload = { mode: mode, use_web_search: webSearchEl.checked };
        if (mode === 'variety') {
            payload.crop_id = cropIdEl.value;
            payload.variety_name = nameEl.value.trim();
        } else {
            payload.crop_name = nameEl.value.trim();
            payload.crop_type = cropTypeEl ? cropTypeEl.value.trim() : '';
        }
        return payload;
    }

    function generate() {
        hideError();
        resultWrap.classList.add('d-none');
        setApplyEnabled(false);

        var current = new AbortController();
        controller = current;
        startProgress();

        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildPayload()),
            signal: current.signal
        })
            .then(function (res) {
                return res.json().catch(function () {
                    return { ok: false, error: 'サーバーから不正な応答がありました（HTTP ' + res.status + '）' };
                });
            })
            .then(function (data) {
                if (controller !== current) return;  // 中断・やり直し済みの古い応答は捨てる
                if (data.ok) {
                    resultEl.value = data.markdown;
                    resultWrap.classList.remove('d-none');
                    setApplyEnabled(true);
                } else {
                    showError(data.error || '生成に失敗しました', data.need_settings);
                }
            })
            .catch(function (err) {
                if (err.name === 'AbortError' || controller !== current) return;
                showError('通信エラーが発生しました。もう一度お試しください');
            })
            .finally(function () {
                if (controller === current) {
                    controller = null;
                    stopProgress();
                }
            });
    }

    function apply(how) {
        var draft = resultEl.value.trim();
        if (!draft) return;
        if (how === 'replace') {
            notesEl.value = draft;
        } else {
            var existing = notesEl.value.replace(/\s+$/, '');
            notesEl.value = existing ? existing + '\n\n' + draft : draft;
        }
        modal.hide();
        notesEl.focus();
    }

    btn.addEventListener('click', function () {
        if (!validate()) return;
        resetModal();
        modal.show();
    });
    webSearchEl.addEventListener('change', updateEstimate);
    generateBtn.addEventListener('click', generate);
    appendBtn.addEventListener('click', function () { apply('append'); });
    replaceBtn.addEventListener('click', function () { apply('replace'); });
    modalEl.addEventListener('hidden.bs.modal', function () {
        if (controller) {
            controller.abort();
            controller = null;
            stopProgress();
        }
    });
})();
```

- [ ] **Step 5: 作物フォームに組み込む** — `app/templates/crops/form.html`

メモ欄の `<label for="notes" class="form-label">メモ</label>` を次に置き換える:
```html
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <label for="notes" class="form-label mb-0">メモ</label>
                            {% set ai_mode = 'crop' %}
                            {% include '_ai_notes_button.html' %}
                        </div>
```

`{% include '_photo_pool_picker_modal.html' %}` の次の行に追加:
```html
{% include '_ai_notes_modal.html' %}
```

`extra_js` の `<script src="{{ url_for('static', filename='js/photo-pool-picker.js') }}"></script>` の次の行に追加:
```html
<script src="{{ url_for('static', filename='js/ai-notes.js') }}"></script>
```

`ai_mode` は `{% block content %}` 内で set しているので、同じブロック内にある `_ai_notes_modal.html` の include からも見える。

- [ ] **Step 6: 品種フォームに組み込む** — `app/templates/varieties/form.html`

メモ欄の `<label for="notes" class="form-label">メモ</label>` を次に置き換える:
```html
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <label for="notes" class="form-label mb-0">メモ</label>
                            {% set ai_mode = 'variety' %}
                            {% include '_ai_notes_button.html' %}
                        </div>
```

`{% include '_crop_select_multi_modal.html' %}` の次の行に `{% include '_ai_notes_modal.html' %}` を、`extra_js` の `photo-pool-picker.js` の次の行に `<script src="{{ url_for('static', filename='js/ai-notes.js') }}"></script>` を追加する。

- [ ] **Step 7: 描画テストが通ることを確認する**

Run: `uv run pytest -v`
Expected: すべて PASS

- [ ] **Step 8: ブラウザで手動確認する（APIキー無し・ダミーキー）**

実 API は課金されるため、ここでは課金されない範囲だけ確認する。

1. `docs/db-validation-safety.md` の手順で `instance/garden.db` をバックアップする（起動時に 020 マイグレーションが実データ DB に適用されるため）
2. `.env` に `ANTHROPIC_API_KEY` が無い状態で `uv run python run.py` を起動
3. `/crops/new`: ボタンが無効、ツールチップ「APIキーが未設定のため使えません」、「設定画面で確認」リンクで `/settings/` へ移動できる
4. `/settings/`: 「未設定」と手順が表示される。地域に「神奈川県（温暖地）露地」を入れて保存 → 「設定を保存しました」
5. サーバーを止め、`.env` に `ANTHROPIC_API_KEY=sk-ant-dummy` を書いて再起動（無効なキーなので課金されない）
6. `/crops/new`:
   - 作物名が空のままボタン → 作物名欄が赤枠＋「作物名を入力してください」、フォーカス移動、モーダルは開かない
   - 作物名に空白だけ → 同じ挙動
   - 作物名「ミニトマト」→ モーダルが開き、Webで調べるが OFF、目安「10〜30秒・約10円」。チェックを入れると目安が切り替わる
   - 「生成」→ スピナーと経過秒数 → 「APIキーが無効です。.env を確認してください」が赤いアラートで出る。アラートが勝手に消えない
7. `/varieties/new`:
   - 親作物未選択でボタン → 親作物欄が赤枠＋「親作物を選択してください」
   - 親作物を選び品種名が空 → 品種名欄が赤枠
   - 両方入力 → モーダルが開き、Webで調べるが ON、対象が「品種名（作物名）」
8. 古い応答の上書き確認（Review Focus 4）: 開発者ツールの Network で回線を「Slow 3G」にし、「生成」直後にモーダルを閉じ、すぐ開き直す → 前のリクエストが canceled になり、開き直したモーダルにエラーや結果が出ない
9. 地域を空にして保存 → 品種フォームで生成 → 「先に設定画面で地域・栽培環境を登録してください」と「設定画面を開く」リンク
10. 確認後、`.env` のダミーキーを消し、地域を元に戻す

反映動作（置き換え／追記）は Task 7 の実 API 確認で行う。

- [ ] **Step 9: Commit**

```bash
git add app/templates/_ai_notes_button.html app/templates/_ai_notes_modal.html app/static/js/ai-notes.js app/templates/crops/form.html app/templates/varieties/form.html tests/test_settings_routes.py
git commit -m "作物・品種フォームに AI 下書きボタンとモーダルを追加"
```

---

### Task 6: ドキュメント更新

**Files:**
- Modify: `app/models/CLAUDE.md`（テーブル一覧＋主要テーブル詳細）
- Modify: `app/routes/CLAUDE.md`（URL設計表）
- Modify: `CLAUDE.md`（主な機能）
- Create: `docs/frontend/ai-notes.md`
- Modify: `app/templates/CLAUDE.md`（ガイド一覧表）
- Modify: `README.md`（機能・セットアップ）

**Interfaces:**
- Consumes: Task 1〜5 の成果物（名前はそのまま記載する）
- Produces: なし

- [ ] **Step 1: `app/models/CLAUDE.md`**

テーブル一覧表の `supplements` 行の後に追加:
```markdown
| app_settings | アプリ設定（キーバリュー形式。`region` = 地域・栽培環境） | key |
```

主要テーブル詳細の末尾に追加:
```markdown
#### app_settings
| カラム | 型 | 説明 |
|--------|-----|------|
| key | TEXT | 主キー（設定名）。現在の使用キー: `region`（AIメモ下書きの地域・栽培環境） |
| value | TEXT | 設定値 |
| updated_at | TIMESTAMP | 更新日時 |

`AppSettings.get(key, default=None)` / `AppSettings.set(key, value)`（upsert）でアクセスする。APIキーなどの秘密情報はここに保存しない（`.env` で管理）。
```

- [ ] **Step 2: `app/routes/CLAUDE.md`**

URL設計表の写真プール行の後に追加:
```markdown
| 設定 | settings | - | - | - | GET/POST /settings/ |
```

表の下の補足段落の後に追加:
```markdown
`settings` Blueprint は設定画面に加え、作物・品種フォーム共通の AI メモ下書き API `POST /settings/ai/notes-draft`（JSON）を持つ。リクエストは `{"mode": "crop", "crop_name", "crop_type", "use_web_search"}` または `{"mode": "variety", "crop_id", "variety_name", "use_web_search"}`。成功 200 `{"ok": true, "markdown"}`、入力不備 400（地域未設定は `need_settings: true`）、生成失敗 502。Claude API 呼び出しは `app/utils/ai_notes.py` に集約している。
```

- [ ] **Step 3: ルート `CLAUDE.md`**

「主な機能」の作物管理の行の後に追加:
```markdown
- **AIメモ下書き:** 作物・品種フォームの「✨ AIで下書き」から Claude API でメモの下書き（設定画面の地域・栽培環境を基準にした時期、特性、栽培のコツ）を生成し、モーダルで確認して置き換え／追記できる。「Webで調べる」（品種は既定ON）で Web 検索を併用し参考URLを付与。APIキーは `.env` の `ANTHROPIC_API_KEY`、モデルは `ANTHROPIC_MODEL`（`claude-opus-5-5` 既定 / `claude-sonnet-5-5`）。地域は設定画面（`/settings/`）で `app_settings` テーブルに保存。実装は `app/utils/ai_notes.py` + `settings_routes.py` + `_ai_notes_button.html` / `_ai_notes_modal.html` / `ai-notes.js`
```

「開発サーバー起動」セクションの後に追加:
```markdown
## テスト

```bash
uv run pytest
```

テストは `tests/conftest.py` のフィクスチャで tmp_path 上の使い捨て DB を使う（`instance/garden.db` には触れない）。Claude API はフェイククライアントで差し替え、実 API は呼ばない。
```

- [ ] **Step 4: `docs/frontend/ai-notes.md` を作る**

```markdown
# AI メモ下書き（作物・品種フォーム）

作物・品種フォームのメモ欄で、Claude API による下書き生成を行う部品。

## 部品

| ファイル | 役割 |
|---|---|
| `app/templates/_ai_notes_button.html` | メモ欄ラベル横のボタン。`ai_available` が false なら無効化＋ツールチップ＋設定画面リンク |
| `app/templates/_ai_notes_modal.html` | 下書きモーダル（Webで調べる・目安表示・生成・結果テキストエリア・置き換え／追記／破棄） |
| `app/static/js/ai-notes.js` | 入力チェック、`POST /settings/ai/notes-draft` 呼び出し、反映 |

## 組み込み方

`{% block content %}` 内で `ai_mode` を set してからボタンとモーダルを include し、`extra_js` で JS を読み込む。

```html
{% set ai_mode = 'crop' %}   {# 品種フォームは 'variety' #}
{% include '_ai_notes_button.html' %}
...
{% include '_ai_notes_modal.html' %}
...
<script src="{{ url_for('static', filename='js/ai-notes.js') }}"></script>
```

JS が参照する既存要素 ID: `notes`, `name`, `crop_type`（作物）、`crop_id_hidden` / `selected-crop-display` / `crop-select-error`（品種）。

## 挙動のルール

- ボタンは APIキー未設定時のみ無効。名前が空などの入力不備は押下時に該当欄を赤枠にして知らせる（無効化しない）
- Webで調べるの初期値: 品種 ON、作物 OFF。目安は `ai_model_info.estimate_on/off`
- 生成中にモーダルを閉じるとリクエストを中断し、古い応答は表示しない
- 反映はフォームのテキストエリアまで。DB 保存はフォームの保存ボタン
- モーダル内アラートは `alert-permanent` 必須（`main.js` が通常の `.alert` を自動で閉じるため）
- 動的な文言は `textContent` で設定する
```

- [ ] **Step 5: `app/templates/CLAUDE.md`**

ガイド一覧表の最後の行の後に追加:
```markdown
| [`docs/frontend/ai-notes.md`](../../docs/frontend/ai-notes.md) | 作物・品種フォームの AI メモ下書き（ボタン・モーダル・`ai-notes.js`） |
```

- [ ] **Step 6: `README.md`**

`## 機能` セクションの作物管理の項目の後に、ルート CLAUDE.md と同趣旨の「AIメモ下書き」の説明を利用者向けの言葉で追加する（例: 「作物・品種のメモを AI が下書き。設定画面で地域を登録すると、その地域に合わせた植え付け・収穫時期を提案します」）。

`## セットアップ` の「3. 開発サーバー起動」の前に次の節を追加し、以降の番号を繰り下げる:
```markdown
### 3. AI機能の設定（任意）

メモの AI 下書きを使う場合は、Anthropic Console（console.anthropic.com）で API キーを発行し、プロジェクト直下に `.env` を作成します。

```
ANTHROPIC_API_KEY=発行したキー
# 任意: claude-opus-5-5（既定・品質重視）または claude-sonnet-5-5（コスト・速度重視）
ANTHROPIC_MODEL=claude-opus-5-5
```

起動後、ナビバーの「設定」で地域・栽培環境を登録してください。API の利用料は 1 件あたり約5〜40円です（モデルと Web 検索の有無による）。
```

`## プロジェクト構造` にファイル単位の一覧がある場合は、`app/utils/ai_notes.py`、`app/routes/settings_routes.py`、`app/templates/settings/`、`tests/` を既存の書式に合わせて追記する。

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md app/models/CLAUDE.md app/routes/CLAUDE.md app/templates/CLAUDE.md docs/frontend/ai-notes.md README.md
git commit -m "AIメモ下書き機能のドキュメントを追加"
```

---

### Task 7: 実 API での動作確認（APIキー発行後・課金あり）

**前提:** ユーザーが API キーを発行し `.env` に設定済みであること。課金が発生するので、実行前にユーザーの了承を得る。キーが未発行ならこのタスクは保留にしてユーザーに伝える。

**Files:** なし（確認のみ。問題が見つかれば該当タスクのファイルを修正し、テストを追加してからコミット）

- [ ] **Step 1: 作物・Web検索 OFF（約10円）**

`/crops/<既存のメモが空の作物>/edit` で生成 → 見出し構成（植え付け時期／収穫時期／特性／栽培のコツ）どおり、時期が設定した地域基準、参考URL セクションが無いことを確認。メモ欄が空なので「置き換える」が強調表示 → 押すとメモ欄に入る。保存せず「キャンセル」で DB が変わらないことを確認。

- [ ] **Step 2: 品種・Web検索 ON（約35〜40円）**

`/varieties/<既存の品種>/edit` で生成 → 品種固有の特徴が中心、末尾に「## 参考URL」があり、各リンクが実在するページに飛ぶことを確認。既存メモがある状態で「末尾に追記する」→ 空行を挟んで追加されること。

- [ ] **Step 3: サーバーログの確認**

`AI notes request_id=... stop_reason=end_turn` が出力されていること。

- [ ] **Step 4（任意）: Sonnet 5.5 への切り替え**

`.env` に `ANTHROPIC_MODEL=claude-sonnet-5-5` → 再起動 → 設定画面とモーダルのモデル表示・目安が切り替わること。1 件生成して品質を比較。確認後は元に戻すかユーザーの判断に任せる。
