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
