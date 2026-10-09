# API の curl 例

段階ごとの動作確認用。エージェント PC（Ubuntu）またはメイン PC の Git Bash で実行する。

```bash
# Windows 暫定期（移設後は http://127.0.0.1:5001/api/v1）
export GARDEN_API_URL=http://192.168.11.24:5001/api/v1
export GARDEN_API_TOKEN='（.env の API_TOKEN）'
gapi() { curl -sS -H "Authorization: Bearer $GARDEN_API_TOKEN" "$@"; echo; }
```

## 疎通確認

```bash
gapi "$GARDEN_API_URL/health"
# → {"ok": true, "data": {"status": "ok"}}
curl -sS "$GARDEN_API_URL/health"   # トークンなし → 401
```

## 作物（/crops）

```bash
gapi "$GARDEN_API_URL/crops?q=トマト"                                   # 一覧・検索
gapi "$GARDEN_API_URL/crops/1"                                           # 詳細
gapi -X POST "$GARDEN_API_URL/crops" -H 'Content-Type: application/json' \
     -d '{"name":"ミニトマト","crop_type":"ナス科"}'                      # 作成
gapi -X POST "$GARDEN_API_URL/crops" \
     -F 'data={"name":"なす","crop_type":"ナス科"}' -F image=@nasu.jpg   # 画像付きで作成
gapi -X PATCH "$GARDEN_API_URL/crops/1" -H 'Content-Type: application/json' \
     -d '{"notes":"脇芽はこまめに摘む"}'                                  # 部分更新
gapi -X POST "$GARDEN_API_URL/crops/1/images" -F extra_images=@a.jpg -F extra_images=@b.jpg  # 追加画像
gapi -X POST "$GARDEN_API_URL/crops" -H 'Content-Type: application/json' -d '{"nmae":"x"}'   # → 422 の例
```

## 選択肢・名前検索

```bash
gapi "$GARDEN_API_URL/meta"                                   # 選択肢の一覧（最初に読む）
gapi -G "$GARDEN_API_URL/lookup" --data-urlencode 'q=ミニトマト'  # 名前 → ID
gapi -G "$GARDEN_API_URL/lookup" --data-urlencode 'q=南' -d types=location
```

## 品種（/varieties）

```bash
gapi "$GARDEN_API_URL/varieties?crop_id=1"
gapi -X POST "$GARDEN_API_URL/varieties" -H 'Content-Type: application/json' \
     -d '{"crop_id":1,"name":"アイコ"}'
gapi -X PATCH "$GARDEN_API_URL/varieties/3" -H 'Content-Type: application/json' -d '{"notes":"甘い"}'
```

## 場所（/locations）

```bash
gapi "$GARDEN_API_URL/locations"
gapi -X POST "$GARDEN_API_URL/locations" -F 'data={"name":"ベランダ","location_type":"プランター","sun_exposure":"半日"}' -F image=@veranda.jpg
gapi -X PATCH "$GARDEN_API_URL/locations/2" -H 'Content-Type: application/json' -d '{"area_size":3.5}'
```

## 植え付け（/plantings）

```bash
gapi -G "$GARDEN_API_URL/plantings" --data-urlencode 'q=アイコ'          # 栽培中（既定 status=active）
gapi "$GARDEN_API_URL/plantings?status=all&location_id=1"
gapi -X POST "$GARDEN_API_URL/plantings" -H 'Content-Type: application/json' \
     -d '{"location_id":1,"variety_id":3,"planted_date":"2026-05-01","quantity":2}'
gapi -X PATCH "$GARDEN_API_URL/plantings/5" -H 'Content-Type: application/json' -d '{"quantity":3}'
gapi -X POST "$GARDEN_API_URL/plantings/5/end" -H 'Content-Type: application/json' -d '{"end_date":"2026-10-09"}'
```

## 栽培記録（/planting_records）

```bash
gapi "$GARDEN_API_URL/planting_records?planting_id=5"
gapi -X POST "$GARDEN_API_URL/planting_records" \
     -F 'data={"planting_id":5,"recorded_at":"2026-10-09","notes":"花が咲いた"}' -F image=@flower.jpg
```

## 収穫（/harvests）

```bash
gapi "$GARDEN_API_URL/harvests?crop_id=1&date_from=2026-07-01"
gapi -X POST "$GARDEN_API_URL/harvests" \
     -F 'data={"planting_id":5,"harvest_date":"2026-10-09","quantity":300,"unit":"g"}' \
     -F image=@harvest.jpg -F extra_images=@harvest2.jpg
```

## 日記・料理・タスク（関連付き）

```bash
gapi -X POST "$GARDEN_API_URL/diary_entries" \
     -F 'data={"title":"初収穫","entry_date":"2026-10-09","weather":"晴れ","content":"甘かった","relations":{"planting_ids":[5],"harvest_ids":[12]}}' \
     -F image=@diary.jpg
# relations は送ったキーだけ置き換え（[] で全解除、送らないキーはそのまま）
gapi -X PATCH "$GARDEN_API_URL/diary_entries/8" -H 'Content-Type: application/json' -d '{"relations":{"harvest_ids":[]}}'
gapi -X POST "$GARDEN_API_URL/cooking_records" -H 'Content-Type: application/json' \
     -d '{"title":"トマトサラダ","cooked_date":"2026-10-09","category":"サラダ","relations":{"harvest_ids":[12]}}'
gapi -X POST "$GARDEN_API_URL/tasks" -H 'Content-Type: application/json' \
     -d '{"title":"追肥","due_date":"2026-10-10","relations":{"planting_ids":[5]}}'
gapi -X PATCH "$GARDEN_API_URL/tasks/3" -H 'Content-Type: application/json' -d '{"status":"completed"}'
```

## 写真プール（/photos）

```bash
gapi -X POST "$GARDEN_API_URL/photos" -F files=@IMG_1.jpg -F files=@IMG_2.jpg -F 'data={"notes":"10/9 畑"}'
gapi "$GARDEN_API_URL/photos?unused=true"
# プールの写真を本体画像・追加画像として使う
gapi -X POST "$GARDEN_API_URL/harvests" -H 'Content-Type: application/json' \
     -d '{"planting_id":5,"harvest_date":"2026-10-09","quantity":300,"unit":"g","photo_pool_id":21,"extra_photo_pool_ids":[22]}'
```
