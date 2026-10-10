# やりたいことリスト

ユーザーがやりたいと言った作業・検証の一覧（不具合や見送った改善は [`known-issues.md`](known-issues.md)）。着手したら「状態」を更新し、終わったら行を削除する。

| 登録日 | やりたいこと | 背景・メモ | 状態 |
|---|---|---|---|
| 2026-10-10 | Hermes を無料モデルで使えるか検証する | .24 の Hermes は OpenRouter の `anthropic/claude-haiku-5.5`（有料）。補助モデル（auxiliary）の設定はなく、同じ Haiku が使われている。OpenRouter の `:free` モデルからツール呼び出しに対応するものを 2〜3 個選び、`hermes --model <モデル名>` で Haiku と同じ依頼（health → 作物一覧 → 植え付けを名前で探す・候補が複数なら確認 → 写真付きの栽培記録・収穫・日記）を試して比べる。使えればメインと `auxiliary`（`auxiliary.free_only: true` など）の両方を無料にする。無料モデルは回数制限と、何段階もの操作の誤りに注意 | 未着手 |
| 2026-10-10 | アプリを Ubuntu（.24）へ移設する | 手順は [`api/migration-to-ubuntu.md`](api/migration-to-ubuntu.md)。Hermes が `pika3` で動いている点に注意（手順書 §6） | 未着手 |
| 2026-10-10 | Telegram の「ファイル」送信（HEIC）に対応する | 「写真」として送ると撮影日時が消え、縮小される。「ファイル」なら元の画質と撮影日時が残るが、iPhone では HEIC のまま届き API が 415 にする（[`api/hermes-telegram.md`](api/hermes-telegram.md)）。設計: `pillow-heif` を追加し、`save_image` でファイルの中身から HEIC を判定して JPEG（品質90、EXIF は残し、向きは画素に反映して Orientation=1）で保存、API の `check_image` は HEIF を受け付けて jpg 扱い、画面の許可拡張子に heic/heif を追加、SKILL.md の 415 の案内を更新。メイン PC では `pillow-heif` の DLL（libde265 など）が Smart App Control に止められるため、移設後に .24 で実装・テストする。実物の iPhone HEIC で向きと撮影日時を確認すること | 移設待ち |
