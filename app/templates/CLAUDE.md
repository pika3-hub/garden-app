# テンプレート開発ガイド（インデックス）

Jinja2 テンプレートと関連フロントエンド部品（Bootstrap カスタマイズ、共通マクロ、再利用可能な include 部品）の規約。トピックごとに `docs/frontend/` 配下のファイルへ分割している。新規トピックを追加する際は、既存ファイルに継ぎ足すのではなく、1トピック1ファイルの原則に沿って新しいファイルを起こし、下表に追記すること（このファイル自体を肥大化させない）。

## ガイド一覧

| ファイル | カバー範囲 |
|---------|-----------|
| [`docs/frontend/macros-and-labels.md`](../../docs/frontend/macros-and-labels.md) | `base.html` ブロック、使用ライブラリ、作物名・品種名の表記ルール（`crop_display_name` / `crop_label`） |
| [`docs/frontend/images-and-photo-pool.md`](../../docs/frontend/images-and-photo-pool.md) | 画像サムネイル生成、写真プールピッカー、スライドショー機能 |
| [`docs/frontend/dashboard.md`](../../docs/frontend/dashboard.md) | HOME画面（画像カルーセル、直近のタスク、最近の活動タイムライン） |
| [`docs/frontend/detail-pages.md`](../../docs/frontend/detail-pages.md) | 詳細画面の基本情報カード、操作ボタン配置、サイドバー関連カード、前後ナビゲーション |
| [`docs/frontend/list-filtering.md`](../../docs/frontend/list-filtering.md) | 一覧画面のバッジフィルター（レガシー/マルチグループ、モバイルモーダル）、日付・種類グルーピング |
| [`docs/frontend/entity-select-modal.md`](../../docs/frontend/entity-select-modal.md) | エンティティ選択モーダル（複数選択、`MultiSelectModal`） |
| [`docs/frontend/supplements.md`](../../docs/frontend/supplements.md) | 補足情報（テキスト/画像/URL+OGP/YouTube埋め込み） |
| [`docs/frontend/ai-notes.md`](../../docs/frontend/ai-notes.md) | 作物・品種フォームの AI メモ下書き（ボタン・モーダル・`ai-notes.js`） |
| [`docs/frontend/hermes-ask-panel.md`](../../docs/frontend/hermes-ask-panel.md) | 植え付け・作物・品種の詳細画面の「Hermes に聞く」パネル（`_hermes_ask_panel.html`、`hermes-ask.js`、offcanvas、SSE の受け方） |
| [`docs/frontend/hermes-chat.md`](../../docs/frontend/hermes-chat.md) | Hermes とのチャット画面（`/hermes/chat`、会話の一覧・続き・題名変更・削除、ナビ・タブの「チャット」、`hermes-chat.js`） |
| [`docs/frontend/markdown-notes.md`](../../docs/frontend/markdown-notes.md) | メモ欄・補足テキストの Markdown 表示（`markdown` フィルター、`.markdown-body`、対象/対象外の箇所） |

## 編集の入口は `is_owner()` で囲む

ログインしていない人（家族。HTTP の入口では全員）には、登録・編集・削除・アップロード・AI 下書き・「写真プールから選択」などのボタン、リンク、フォーム、新規作成への入口を出さない。`{% if is_owner() %}…{% endif %}`（`app/auth.py` の Jinja グローバル）で囲む。新しい画面を作るときも同じにする。

- これは見た目の整理で、守っているのはサーバー側（GET・HEAD・OPTIONS 以外は既定で拒否）。囲み忘れても漏れはしないが、押すとログイン画面へ案内されるだけの無駄なボタンが出る
- POST のフォームには `csrf.js` が CSRF の隠し項目を自動で足す。JS で後から作った POST のフォームを `form.submit()` で送る場合と、GET のフォームの `formmethod="post"` のボタンは自動では付かない（詳しくは `app/routes/CLAUDE.md` の「ログインと新しいルートの規約」）
- ナビの右端はログインしていなければ「ログイン」、ログイン中は「ログアウト」。設定画面にパスキーの欄がある

## フォームの初期値は NULL を空文字にする

編集フォームで nullable なカラムを初期値に出すときは `{{ (crop.notes or '') if crop else '' }}` と書く。`{{ crop.notes if crop else '' }}` だと NULL が「None」と表示され、そのまま保存すると文字列 `'None'` が DB に登録される（過去に収穫の単位・作物/品種のメモで発生）。`tests/test_form_empty_values.py` で確認している。

## 料理記録（Cooking）は横断的な機能

`/cooking/` は独立したCRUD画面を持つが、内容の大半は上記の既存ガイドに統合されている（単独のガイドは持たない）。新機能を作物・場所などと同様に既存の共通部品へ統合する際の参考実装:

- ダッシュボードカルーセル対象テーブルの1つ → `dashboard.md`
- サイドバー関連カード（`_related_cookings_card.html`）→ `detail-pages.md`
- エンティティ選択モーダル4種すべてを使用 → `entity-select-modal.md`
- 補足情報対応（`entity_type='cooking'`）→ `supplements.md`
- バッジフィルター・グルーピング → `list-filtering.md`

新しい横断機能を追加するときは、この一覧のように「既存ガイドのどこに追記したか」を一言でまとめておくと、次回の監査で漏れを見つけやすい。
