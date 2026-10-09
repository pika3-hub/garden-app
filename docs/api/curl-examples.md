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
