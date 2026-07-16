# エンティティ選択モーダル（複数選択）

`app/templates/CLAUDE.md` から分割。日記・タスク・料理の登録・編集フォームで、関連エンティティ（作物・品種・場所・植え付け・収穫）をカード型モーダルで複数選択する共通機能。

## 共通JS

`app/static/js/entity-select-modal.js` — `MultiSelectModal` クラス。

## 使い方

```js
new MultiSelectModal({
    modalId: 'cropMultiSelectModal',        // モーダルのDOM id
    cardSelector: '.crop-ms-card',          // 選択可能カードのセレクタ
    idAttribute: 'cropId',                  // card.dataset からID取得するキー
    inputContainerId: 'crop-hidden-inputs', // hidden input 配置コンテナ
    inputName: 'crop_ids',                  // hidden input の name 属性
    displayContainerId: 'selected-crops-display', // バッジチップ表示コンテナ
    badgeRenderer: function(card) { ... },  // カード→バッジHTML生成コールバック
    filterMode: 'legacy',                   // 'legacy'（単一グループ）or 'multi'（マルチグループ）
    filterScope: 'crop-multi',              // legacy用: data-scope 値
    filterCardAttr: 'data-crop-ms-card',    // legacy用: カードのフィルタ属性
});
```

## 動作

- カードクリック → `.ms-card-selected` トグル（チェックマーク表示）
- モーダルフッターの「決定」ボタン → hidden inputs 同期 + バッジチップ描画 + モーダルclose
- バッジチップの「×」→ 選択解除（hidden input 削除、カードハイライト解除）
- 初期化時に既存 hidden inputs を読み取り pre-selected 状態を復元（編集モード対応）

## フィルターモード

| モード | 用途 | 仕組み |
|--------|------|--------|
| `legacy` | 作物・場所モーダル | `data-scope` + `data-filter-type` による単一グループフィルター |
| `multi` | 植え付け・収穫モーダル | `data-ms-filter-card` + `data-ms-filter-group-*` によるマルチグループフィルター（AND/OR） |

モーダル内のフィルターは `badge-filter.js` とは独立してスコープされる（同一ページに複数モーダルがあっても干渉しない）。

## モーダルテンプレート

| テンプレート | Modal ID | 対象画面 | テンプレート変数 |
|------------|----------|---------|----------------|
| `_crop_select_multi_modal.html` | `cropMultiSelectModal` | 日記・タスク | `crops`, `crop_filter_types`, `crop_filter_type_icons`, `selected_crop_ids` |
| `_variety_select_multi_modal.html` | `varietyMultiSelectModal` | 日記・タスク | `varieties`（`apply_inheritance` 適用済み）, `variety_filter_types`, `variety_filter_type_icons`, `selected_variety_ids` |
| `_location_select_multi_modal.html` | `locationMultiSelectModal` | 日記・タスク | `locations`, `location_filter_types`, `selected_location_ids` |
| `_planting_select_multi_modal.html` | `plantingMultiSelectModal` | 日記・タスク・料理 | `active_plantings`, `planting_filter_types`, `planting_filter_type_icons`, `planting_filter_locations`, `selected_location_crop_ids` |
| `_harvest_select_multi_modal.html` | `harvestMultiSelectModal` | 日記・料理 | `harvests`, `harvest_filter_types`, `harvest_filter_type_icons`, `harvest_filter_locations`, `selected_harvest_ids` |

`cooking/form.html` は作物・品種・植え付け・収穫の4モーダルすべてを使用する（料理と各エンティティの多対多関連付けのため）。

## ルートでの実装パターン

各ルートでフィルターデータを計算して `render_template` に渡す。`diary_routes.py` と `task_routes.py` にそれぞれ `_build_filter_data()` ヘルパーがある。

```python
active_plantings = Planting.get_all_with_stats(status='active')
filter_data = _build_filter_data(crops, locations, active_plantings, harvests)
render_template('diary/form.html', ..., **filter_data)
```

編集時は `selected_crop_ids`, `selected_location_ids`, `selected_location_crop_ids`, `selected_harvest_ids`（文字列IDのリスト）も追加で渡す。

## CSSクラス

| クラス | 役割 |
|--------|------|
| `.ms-card-selected` | 選択中カード（チェックマーク付きアウトライン） |
| `.selected-items-chips` | バッジチップコンテナ（空時は「未選択」表示） |
| `.selected-item-chip` | 個別バッジチップ（丸型、×ボタン付き） |
| `.ms-modal-footer` | モーダルフッター（件数 + 決定ボタン） |
