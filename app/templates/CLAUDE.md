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
| [`docs/frontend/markdown-notes.md`](../../docs/frontend/markdown-notes.md) | メモ欄・補足テキストの Markdown 表示（`markdown` フィルター、`.markdown-body`、対象/対象外の箇所） |

## 料理記録（Cooking）は横断的な機能

`/cooking/` は独立したCRUD画面を持つが、内容の大半は上記の既存ガイドに統合されている（単独のガイドは持たない）。新機能を作物・場所などと同様に既存の共通部品へ統合する際の参考実装:

- ダッシュボードカルーセル対象テーブルの1つ → `dashboard.md`
- サイドバー関連カード（`_related_cookings_card.html`）→ `detail-pages.md`
- エンティティ選択モーダル4種すべてを使用 → `entity-select-modal.md`
- 補足情報対応（`entity_type='cooking'`）→ `supplements.md`
- バッジフィルター・グルーピング → `list-filtering.md`

新しい横断機能を追加するときは、この一覧のように「既存ガイドのどこに追記したか」を一言でまとめておくと、次回の監査で漏れを見つけやすい。
