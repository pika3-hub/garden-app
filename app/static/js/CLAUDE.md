# フロントエンドJS開発ガイド

バニラJS（フレームワークなし）で実装された UI 部品。大きい順に `canvas-editor.js` / `canvas-preview.js` / `canvas-fullscreen.js`（見取り図系）、`entity-select-modal.js`（複数選択モーダル）、`badge-filter.js`（一覧フィルター）、`slideshow.js` / `lightbox.js` など。

## 見取り図機能

### アーキテクチャ

| コンポーネント | ファイル | 役割 |
|------------|--------|------|
| エディター画面 | `locations/canvas.html` + `canvas-editor.js` | 作物配置の編集（800×800px） |
| 植え付け配置ページ | `plantings/place.html` + `canvas-placement.js` | 植え付け登録後の見取り図配置（エディターを再利用） |
| プレビューコンポーネント | `locations/_canvas_preview.html` + `canvas-preview.js` | 読み取り専用の表示（400×400px） |
| フルスクリーン表示 | `canvas-fullscreen.js` + `canvas-fullscreen.css` | プレビュークリックで拡大表示（日付ナビ付き） |
| CSSスタイル | `static/css/canvas.css` | エディター・プレビュー共通スタイル |

### 背景画像

- **保存場所**: `app/static/images/location_bg_images/`（静的ファイル、アップロード不可）
- **追加方法**: 画像ファイルを直接このフォルダに配置する（`bg_image_001.png` などの連番命名）
- **対応形式**: `.png`, `.jpg`, `.jpeg`, `.webp`
- **選択UI**: `Location.get_bg_images()` でファイル一覧を取得し、エディター画面でセレクト
- **デフォルト**: `bg_image_default.png`

### 作物アイコン

- **保存場所**: `app/static/images/crop_icons/`
- **命名規則**: `icon_{row:02d}_{col:02d}.png`（例: `icon_01_03.png`）
- **生成元**: スプライトシートを `split_sprite.py` で分割（12列×7行 = 84アイコン）

### データ形式（version 2.0 JSON）

```json
{
  "version": "2.0",
  "placements": [
    {
      "locationCropId": 1,
      "cropId": 5,
      "x": 350,
      "y": 420,
      "iconPath": "icon_01_03.png",
      "imageColor": "#4CAF50",
      "cropName": "トマト",
      "variety": "ミニトマト"
    }
  ]
}
```

- `canvas_data` カラム（`locations` テーブル、TEXT型）に JSON 文字列として保存
- 旧形式（Fabric.js の version 1.x）は無視してプレビューを非表示にする

### APIエンドポイント

| エンドポイント | メソッド | 説明 |
|-------------|--------|------|
| `/locations/<id>/canvas` | GET | エディター画面 |
| `/locations/<id>/canvas/data` | GET | 配置データ取得（JSON） |
| `/locations/<id>/canvas/save` | POST | 配置データ保存 |
| `/locations/<id>/canvas/history/range` | GET | 見取り図に変化がある日付一覧（`{dates: [...]}` 形式） |
| `/locations/<id>/canvas/history?date=YYYY-MM-DD` | GET | 指定日付の配置データ（version 2.0 JSON） |

### プレビューコンポーネントの使い方

```html
{% include 'locations/_canvas_preview.html' %}
```

テンプレートに渡す変数:
- `location` — 場所オブジェクト（`location['id']`, `location['bg_image']` を使用）
- `preview_highlight_id`（任意）— ハイライトする `location_crop_id`

`CanvasPreview` クラスのAPI:
- `updateData(data)` — 表示内容をクリアして新しいデータで再描画（フルスクリーン表示等で使用）
- `data-manual-init="true"` 属性 — 自動初期化をスキップ（JS側で手動制御する場合に指定）

### フルスクリーン表示

見取り図プレビューをクリックすると `canvas-fullscreen.js` でフルスクリーン表示が開く。
- 場所詳細・植え付け詳細の両方で利用（拡大ボタンは廃止、プレビュークリックで起動）
- 場所詳細では履歴の日付ナビゲーション（前へ/次へボタン＋キーボード左右矢印）が利用可能
- 日付データは `/locations/<id>/canvas/history/range` API から取得
- 位置情報の取得元: active作物は `locations.canvas_data`（複数配置対応）、harvested作物は `plantings.canvas_snapshot`

### レスポンシブ対応（重要）

**座標系は常に800×800px固定。これを変更してはならない。**

作物の配置座標（`x`, `y`）はすべて800×800pxキャンバス上の絶対ピクセル値として保存される。モバイル等で表示領域が狭い場合は、キャンバス要素のサイズは800×800を維持したまま `transform: scale()` で縮小表示する。`width: 100%` 等でキャンバス自体を縮小すると、`overflow: hidden` により端の作物がクリップされて見えなくなる。

**エディター（`canvas-editor.js`）のスケーリング:**
- `ResizeObserver` でラッパー幅を監視し、800px未満なら `transform: scale(factor)` を適用
- `transform-origin: top left` で左上基点に縮小
- ラッパーの高さを縮小後のサイズに合わせて設定（空白防止）
- ドラッグ・ドロップの座標は `_toCanvasCoords()` でスケール補正が必要（`clientX / scale`）
- 保存時の座標は常に800×800基準のまま

**プレビュー（`canvas-preview.js`）のスケーリング:**
- 400×400pxのプレビュー領域を、コンテナ幅に合わせて同様に `transform: scale()` で縮小
- `ResizeObserver` で動的に追従

**CSS上の注意点:**
- `#canvas-area` には `flex-shrink: 0` が必須。flexboxコンテナ内でデフォルトの `flex-shrink: 1` だとキャンバスが縮小され、transform と二重に縮小されてしまう
- モバイルではラッパーに `overflow: hidden`（レイアウト上800×800のままの要素をクリップ）
- モバイルではラッパーに `flex: none`（不要な余白を防ぎ、サイドバーをキャンバス直下に配置）
- モバイルではサイドバーの `overflow-y: visible`（ブラウザスクロールに委ねる）、デスクトップでは `overflow-y: auto`

## 植え付け登録フロー

植え付け登録後、見取り図配置ページへ自動遷移し、作物の配置を促す2ステップ方式。

```
植え付けフォーム（/plantings/plant/new）
  ↓ POST → DBにレコード作成（ID取得）
見取り図配置ページ（/plantings/<id>/place）
  ├─ 新規作物をサイドバーでハイライト表示（.crop-item-new）
  ├─ ドラッグ&ドロップで配置 → 保存 → 植え付け詳細へ
  └─ スキップ → 植え付け詳細へ（配置なしでもOK）
```

- **場所詳細からの植え付け:** 栽培中の作物カード内の「作物を植え付ける」→ `/plantings/plant/new?location_id=<id>`（場所プリセレクト済み）
- **品種詳細からの植え付け:** 「この品種を植え付ける」ボタン → `/plantings/plant/new?crop_id=<id>&variety_id=<id>`（作物・品種プリセレクト済み）
- **品種プルダウン:** 作物を選ぶと JS で該当作物の品種のみに絞り込まれる。品種なしでも登録可能（`variety_id` は nullable）。サーバー側で `variety.crop_id == crop_id` を検証する
- **`canvas-placement.js`:** `canvas-editor.js` の上に載せる薄いラッパー。保存後に植え付け詳細へリダイレクトする動作を追加
- **`canvas-editor.js`:** `window._canvasEditor` でインスタンスを公開、`buildSaveData()` メソッドで保存データを取得可能

## 関連ドキュメント

- エンティティ選択モーダル（`entity-select-modal.js`）: `app/templates/CLAUDE.md`
- 一覧画面のバッジフィルター（`badge-filter.js` / `date-badge-filter.js`）: `app/templates/CLAUDE.md`
- スライドショー（`slideshow.js`）: `app/templates/CLAUDE.md`
