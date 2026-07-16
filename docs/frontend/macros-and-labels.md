# マクロ・作物名表記ルール

`app/templates/CLAUDE.md` から分割。base.html の共通ブロック、使用ライブラリ、作物名・品種名の表記統一ルールを扱う。

## base.html のブロック

- `{% block title %}` — ページタイトル
- `{% block extra_css %}` — 追加CSS読み込み
- `{% block content %}` — メインコンテンツ
- `{% block extra_js %}` — 追加JS読み込み

## 使用ライブラリ

- Bootstrap 5.3（CDN）
- Bootstrap Icons（CDN）
- Pillow（サムネイル生成、Python依存）
- ※ Fabric.js は削除済み（見取り図はバニラJSで実装）

## 作物名の表記ルール

作物名・品種名の表示はアプリ全体で統一されたルールに従う。

### 表記フォーマット

| 条件 | 表示 | 例 |
|------|------|-----|
| 品種あり | `{品種名}（{作物名}）` | ミニトマト（トマト） |
| 品種なし | `{作物名}` | バジル |

### 実装方法: 2層構造

**1. `crop_display_name` — テキスト専用グローバル関数**

`app/__init__.py` で定義・登録。プレーンテキストを返す。`<option>` タグ、`data-*` 属性、`title` 属性など **HTMLが使えない箇所** で使用する。引数 `variety` は品種名の文字列（または None）。呼び出し側は VIEW 経由で `cv.crop_name` と `cv.variety` を取得して渡す。

```html
<!-- プルダウン内（HTMLタグ不可） -->
<option>{{ crop_display_name(planting.crop_name, planting.variety) }}</option>
```

**2. `crop_label` — アイコン付きHTML用マクロ**

`app/templates/_macros.html` で定義。作物アイコン（丸型、イメージカラーボーダー、白背景）＋ `crop_display_name` テキストを返す。**HTML表示箇所** で使用する。

```html
{% from '_macros.html' import crop_label %}

<!-- カードタイトル、ナビラベル等 -->
{{ crop_label(crop.crop_name, crop.variety, crop.icon_path, crop.image_color) }}
```

引数: `name`, `variety`, `icon_path`（任意）, `image_color`（任意）

**CSSクラス**: `.crop-icon-inline`（`custom.css` で定義、22px丸型、白背景、イメージカラーボーダー）

### 適用範囲

| 対象 | 方式 | 備考 |
|------|------|------|
| HTML表示（カードタイトル、ヘッダ、ナビラベル、一覧等） | `crop_label` マクロ | アイコン＋テキスト |
| `<select>` / `<option>` 内 | `crop_display_name` 関数 | テキストのみ（HTML不可） |
| `data-*` / `title` 属性 | `crop_display_name` 関数 | テキストのみ |
| カレンダーモーダル（JS動的生成） | JS側で `item.icon_path` を参照 | `calendar.js` で生成 |
| 見取り図サイドバー（エディター・配置ページ） | `crop_display_name` 関数 | テキストのみ |
| 作物一覧（カードタイトル） | `crop_label` マクロ | アイコン＋テキスト、`variety=None` を渡す |
| 品種一覧（カードタイトル） | `crop_label` マクロ | アイコン＋テキスト、`effective_icon_path` / `effective_image_color` で継承反映 |
| 作物エンティティ画面（登録・編集） | アイコン表示なし | `crop_display_name` のみ使用 |

### クエリ要件

`crop_label` マクロは `icon_path` / `image_color` を引数に取るので、モデルのクエリで該当カラムを SELECT する必要がある。ソースは画面によって異なる：

- **植え付け・収穫・カレンダー等**: `crop_variety_view cv` から `cv.crop_name, cv.variety, cv.icon_path, cv.image_color`（品種の外観が優先、未設定なら親作物に継承される）
- **作物一覧・作物詳細**: `crops` テーブルから `c.icon_path, c.image_color`。品種情報は持たないので `crop_label(c.name, None, ...)` の形で呼ぶ
- **品種一覧・品種詳細**: `Variety.apply_inheritance()` により付与される `effective_icon_path` / `effective_image_color`

新規クエリ追加時は、`cv.*` のワイルドカード展開ではなくカラムを明示すること（`app/models/CLAUDE.md` の Row 重複カラム名問題を参照）。
