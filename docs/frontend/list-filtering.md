# 一覧画面のバッジフィルター・グルーピング表示

`app/templates/CLAUDE.md` から分割。一覧画面（作物・品種・場所・植え付け・収穫・料理・タスク・日記）のクライアントサイドフィルターとサーバーサイドグルーピングの規約。

## 一覧画面のバッジフィルター

作物・品種・場所・植え付け・収穫・料理の一覧画面では、種類バッジによるクライアントサイドフィルター（`badge-filter.js`）を提供する。日記・タスクは年・季節・月（タスクはステータスも）のバッジによるクライアントサイドフィルター（`date-badge-filter.js`、規約はファイル冒頭のコメント参照）を使う。日記・タスク・料理はこれとは別にサーバーサイドのキーワード検索（`?keyword=`）を持つ。

### 2つのモード

共通JS `app/static/js/badge-filter.js` が2つのモードを自動判定する:

**レガシーモード（作物一覧・品種一覧・場所一覧）:** `#badge-filter-container` + `data-filter-type` による単一グループフィルター。OR論理（複数選択でいずれかに一致）。

**マルチグループモード（植え付け一覧・収穫一覧・料理一覧）:** `.badge-filter-group[data-filter-key]` による複数グループフィルター。グループ間AND・グループ内OR。カードは `data-filter-card` + `data-filter-group-{key}` 属性を使用。

### 各画面のフィルター対象

| 画面 | モード | フィルター対象 | ルートで渡す変数 |
|------|--------|-------------|----------------|
| 作物一覧 | レガシー | `crop_type` | `filter_types` |
| 品種一覧 | レガシー | `crop_type` | `filter_types` |
| 場所一覧 | レガシー | `location_type` | `filter_types` |
| 植え付け一覧 | マルチグループ | `crop_type` + `location_name` | `filter_types`, `filter_locations` |
| 収穫記録一覧 | マルチグループ | `crop_type` + `location_name` | `filter_types`, `filter_locations` |
| 料理一覧 | マルチグループ | `crop_type` + `category` | `filter_crop_types`, `filter_crop_type_icons`, `categories` |

### モバイル用フィルターモーダル

作物・品種・場所・植え付け・収穫・料理の各一覧画面（`app/templates/*/list.html`）は、バッジフィルターUIをBootstrapモーダル（`#badgeFilterModal`）でラップし、モバイル幅（`d-md-none`）でのみトグルボタン（`.badge-filter-toggle-btn` + `#badge-filter-toggle`、選択中を示す `.badge-filter-toggle-dot`）から開く。デスクトップではバッジフィルターがそのままインライン表示される。新規の一覧画面を追加する際もこのモーダルラッパーを踏襲すること。

### テンプレートでの使い方

**レガシーモード（作物・場所一覧）:**

```html
{% if filter_types %}
<div id="badge-filter-container" class="badge-filter-container">
    {% for t in filter_types %}
    <span class="badge badge-filter badge-filter-inactive" data-type="{{ t }}">{{ t }}</span>
    {% endfor %}
</div>
{% endif %}

<!-- カードラッパーに data-filter-type を付与 -->
<div class="col-md-6 col-lg-4 mb-3" data-filter-type="{{ item.crop_type }}">
```

**マルチグループモード（植え付け・収穫一覧）:**

```html
{% if filter_types or filter_locations %}
<div class="badge-filter-multi">
    {% if filter_types %}
    <div class="badge-filter-group" data-filter-key="cropType">
        <span class="badge-filter-group-label">種類:</span>
        {% for t in filter_types %}
        <span class="badge badge-filter badge-filter-inactive" data-type="{{ t }}">{{ t }}</span>
        {% endfor %}
    </div>
    {% endif %}
    {% if filter_locations %}
    <div class="badge-filter-group" data-filter-key="locationName">
        <span class="badge-filter-group-label">場所:</span>
        {% for loc in filter_locations %}
        <span class="badge badge-filter badge-filter-inactive" data-type="{{ loc }}">{{ loc }}</span>
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endif %}

<!-- カードラッパーに data-filter-card + data-filter-group-* を付与 -->
<div class="col-md-6 col-lg-4 mb-3" data-filter-card data-filter-group-crop-type="{{ item.crop_type }}" data-filter-group-location-name="{{ item.location_name }}">
```

**共通（件数・0件メッセージ）:**

```html
<p class="text-muted mb-3"><span id="filter-count" data-suffix="件の作物">{{ items|length }}件の作物</span></p>
<div id="filter-empty-msg" class="alert alert-info" style="display:none;">
    <i class="bi bi-info-circle"></i> 該当する項目がありません。
</div>
```

CSSクラス: `.badge-filter-container`, `.badge-filter-multi`, `.badge-filter-group`, `.badge-filter-group-label`, `.badge-filter`, `.badge-filter-active`, `.badge-filter-inactive`（`custom.css` で定義）

## 一覧画面のグルーピング表示

主要な一覧画面はサーバー側で `itertools.groupby` を使いセクションごとにグループ化して表示する。各グループは `<section class="date-group">` + `<h3 class="date-group-heading">` で描画し、グループ間の区切りを視覚化する。

### 各画面のグループ化ルール

| 画面 | ルート変数 | グループキー | グループ順 | 見出し |
|------|-----------|-------------|----------|--------|
| 日記一覧 | `grouped_entries` | `entry_date` の `YYYY-MM` | `entry_date DESC`（新しい月が上） | `YYYY年M月` |
| 植え付け一覧 | `grouped_crops` | `planted_date` の `YYYY-MM` | `planted_date DESC` | `YYYY年M月` |
| 収穫記録一覧 | `grouped_harvests` | `harvest_date` の `YYYY-MM` | `harvest_date DESC` | `YYYY年M月` |
| 料理一覧 | `grouped_items` | `cooked_date` の `YYYY-MM` | `cooked_date DESC` | `YYYY年M月` |
| 作物一覧 | `grouped_crops` | `crop_type` | 件数多い順、1件のみは末尾「その他」にまとめる | 作物アイコン（`filter_type_icons`）+ 種類名 |
| 場所一覧 | `grouped_locations` | `location_type` | 件数多い順、1件のみは末尾「その他」にまとめる | 種類名 |
| タスク一覧 | `grouped_tasks` | `status` | `進行中 → 未着手 → 完了`（`Task.get_all()` の ORDER BY） | ステータスバッジ + ラベル + 件数 |

### ルートでの実装パターン

日付グループ（日記・植え付け・収穫）はモデルが既に `{date} DESC` でソート済みのため、そのまま `itertools.groupby` で連続ラン化できる:

```python
def _ym_key(e):
    d = e.get('entry_date')
    return str(d)[:7] if d else ''

grouped_entries = [(k, [item for item in g]) for k, g in groupby(entries, key=_ym_key)]
```

注意: Flask ルート関数名が `list` の場合、ビルトイン `list` がシャドウされるため `list(g)` は `TypeError` になる。内包表記 `[item for item in g]` を使うこと。

種類グループ（作物・場所）は種類キーでソート → グループ化 → 件数降順 → 1件グループを「その他」にマージする:

```python
sorted_crops = sorted(crops, key=_type_key)
grouped_crops = [(k, [item for item in g]) for k, g in groupby(sorted_crops, key=_type_key)]
grouped_crops.sort(key=lambda kv: len(kv[1]), reverse=True)
multi_groups = [kv for kv in grouped_crops if len(kv[1]) > 1]
single_items = [items[0] for _, items in grouped_crops if len(items) == 1]
if single_items:
    multi_groups.append(('その他', single_items))
grouped_crops = multi_groups
```

Pythonの `sorted` は stable のため、種類内の元順序（`created_at DESC`）は保たれる。

### テンプレートでの使い方

```html
{% for key, group_items in grouped_items %}
<section class="date-group" data-group-key="{{ key }}">
    <h3 class="date-group-heading">{{ key }}</h3>
    <div class="row">
        {% for item in group_items %}
        <div class="col-6 col-md-4 col-lg-3 mb-3" data-filter-...>...</div>
        {% endfor %}
    </div>
</section>
{% endfor %}
```

作物一覧の見出しはフィルタバッジと同じアイコンを表示するため `filter_type_icons.get(ct, [])` をループして `<img class="badge-filter-icon">` を先頭に並べる。

### 空グループの自動非表示

フィルターバッジ操作で該当カードが0件になったセクションは見出しごと非表示にする。`badge-filter.js`（マルチグループ・レガシー両モード）と `date-badge-filter.js` の各 `applyFilter()` 末尾に以下を追加している:

```js
var dateGroups = document.querySelectorAll('.date-group');
dateGroups.forEach(function (group) {
    var visible = false;
    group.querySelectorAll('[data-filter-...]').forEach(function (item) {
        if (item.style.display !== 'none') visible = true;
    });
    group.style.display = visible ? '' : 'none';
});
```

対象セレクタは JS ごとに異なる（`[data-filter-year]` / `[data-filter-card]` / `[data-filter-type]`）。

### CSSクラス

| クラス | 役割 |
|--------|------|
| `.date-group` | セクションラッパー（`custom.css` 末尾の `Date Group` セクションで定義） |
| `.date-group-heading` | 見出し（フォレストグリーン下線、`h3` スタイル） |
