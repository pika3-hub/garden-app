# ダッシュボード（HOME画面）

`app/templates/CLAUDE.md` から分割。HOME画面（`index.html`）は統計情報・画像カルーセル・直近のタスク・最近の活動タイムラインの4ブロックで構成される。`app/__init__.py` の `index()` ルート（約280行）がこれらのデータをまとめて構築する。

## レイアウト

統計カード（`col-12 col-md-8`）と画像カルーセル（`col-12 col-md-4`）は上下ではなく**左右並び**（デスクトップ）。モバイルでは縦積みになる。

## 画像カルーセル

**データ取得**: 7テーブル（`crops`, `varieties`, `locations`, `diary_entries`, `harvests`, `planting_records`, `cooking`）から `image_path` が存在するレコードをUNION ALLクエリで最大20件取得し、`random.shuffle()` でランダム化。各画像に `detail_url`（詳細ページURL）、`icon`（種別アイコン）、`type_label`（種別名）を付与してテンプレートに渡す。`harvests` / `planting_records` の作物名・品種名は `crop_variety_view` から取得する。

**実装**:
- **コンポーネント**: Bootstrap 5 標準 Carousel（`data-bs-ride="carousel"`, 4秒間隔自動再生）
- **画像**: サムネイル（`thumb_path` フィルター）使用、`onerror` でオリジナル画像にフォールバック
- **キャプション**: `.carousel-caption.card-photo-overlay`（既存の `.card-photo-overlay` を流用、専用の `.carousel-caption-badge` クラスは存在しない）+ `.carousel-type-icon`（種別アイコン）
- **日付オーバーレイ**: `.card-img-date-overlay` を画像上に表示
- **リンク**: 画像クリックで対応する詳細ページに遷移
- **サイズ**: 固定高さではなく `aspect-ratio: 1/1; height: 100%`（統計カードと高さを揃える正方形レイアウト）
- **画像なし**: `{% else %}` 側で同じ `#dashboardCarousel` のカードに「画像がありません」を表示する

**CSS（`custom.css` の `Dashboard Carousel` セクション）**:

| クラス / セレクター | 役割 |
|---------------------|------|
| `#dashboardCarousel` | コンテナ（角丸、overflow hidden、`aspect-ratio: 1/1`） |
| `#dashboardCarousel:hover` | `.card:hover` の `translateY` を無効化 |
| `.carousel-dashboard-img` | 画像（`object-fit: cover`） |
| `#dashboardCarousel .carousel-caption.card-photo-overlay` | キャプション（`.card-photo-overlay` 流用） |
| `.carousel-type-icon` | キャプション内の種別アイコン |
| `#dashboardCarousel .card-img-date-overlay` | 画像上の日付オーバーレイ |

`.carousel-counter` クラスは `custom.css` に残っているが `index.html` 側にレンダリングされておらず、対応する `#carouselCurrent` 要素も存在しない（orphaned／未使用のレガシーコード）。`index.html` の `extra_js` にも `#carouselCurrent` を探して見つからず即 return するだけのスクリプトが残っている。

## 直近のタスク

`index.html` に、期限順・緊急度でグループ化したタスク一覧セクションがある（`app/__init__.py` の `index()` 内で構築）。

## 最近の活動

5種類のデータソース（日記・植え付け・栽培記録・収穫・料理）を日付・種別でグルーピングしたアクティビティタイムラインを表示する。バッジ・アイコン表示はカルーセルとは別ロジックで `index()` 内に実装されている。
