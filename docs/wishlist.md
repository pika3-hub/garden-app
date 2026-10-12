# やりたいことリスト

ユーザーがやりたいと言った作業・検証の一覧（不具合や見送った改善は [`known-issues.md`](known-issues.md)）。着手したら「状態」を更新し、終わったら行を削除する。

| 登録日 | やりたいこと | 背景・メモ | 状態 |
|---|---|---|---|
| 2026-10-12 | Hermes に最新の栽培記録の画像から生育状況を診断してもらう | Hermes は Web 画面（5000番）への接続を ufw で拒否され、`/opt/garden-app` も読めないため、API が返す `image_url` の画像を取得できない。制限は緩めず、API（5001、Bearer 必須）に画像取得のエンドポイント（例: `GET /{種類}/{id}/image`、`?size=thumb` でサムネイル 800×600）を追加する。返すのはそのデータの `image_path` の画像だけ（任意のパスは受け付けない）。SKILL.md に「最新の栽培記録を取る → curl で画像を保存 → `vision_analyze` で見る → 所見を答える（画像を見ずに答えない）」を追記。写真1枚での病害虫の断定は難しいので、所見として伝え、前回の記録と比べさせる案もある | 未着手 |
| 2026-10-10 | Hermes を無料モデルで使えるか検証する | サーバーの Hermes は OpenRouter の `anthropic/claude-haiku-5.5`（有料）。補助モデル（auxiliary）の設定はなく、同じ Haiku が使われている。OpenRouter の `:free` モデルからツール呼び出しに対応するものを 2〜3 個選び、`hermes --model <モデル名>` で Haiku と同じ依頼（health → 作物一覧 → 植え付けを名前で探す・候補が複数なら確認 → 写真付きの栽培記録・収穫・日記）を試して比べる。使えればメインと `auxiliary`（`auxiliary.free_only: true` など）の両方を無料にする。無料モデルは回数制限と、何段階もの操作の誤りに注意 | 未着手 |
| 2026-10-10 | Telegram の「ファイル」送信（HEIC）に対応する | 「写真」として送ると撮影日時が消え、縮小される。「ファイル」なら元の画質と撮影日時が残るが、iPhone では HEIC のまま届き API が 415 にする（[`api/hermes-telegram.md`](api/hermes-telegram.md)）。設計: `pillow-heif` を追加し、`save_image` でファイルの中身から HEIC を判定して JPEG（品質90、EXIF は残し、向きは画素に反映して Orientation=1）で保存、API の `check_image` は HEIF を受け付けて jpg 扱い、画面の許可拡張子に heic/heif を追加、SKILL.md の 415 の案内を更新。メイン PC では `pillow-heif` の DLL（libde265 など）が Smart App Control に止められるため、サーバー（2026-10-11 移設済み）で実装・テストする。実物の iPhone HEIC で向きと撮影日時を確認すること | 未着手 |
