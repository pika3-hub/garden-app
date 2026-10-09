# やりたいことリスト

ユーザーがやりたいと言った作業・検証の一覧（不具合や見送った改善は [`known-issues.md`](known-issues.md)）。着手したら「状態」を更新し、終わったら行を削除する。

| 登録日 | やりたいこと | 背景・メモ | 状態 |
|---|---|---|---|
| 2026-10-10 | Hermes を無料モデルで使えるか検証する | .24 の Hermes は OpenRouter の `anthropic/claude-haiku-5.5`（有料）。補助モデル（auxiliary）の設定はなく、同じ Haiku が使われている。OpenRouter の `:free` モデルからツール呼び出しに対応するものを 2〜3 個選び、`hermes --model <モデル名>` で Haiku と同じ依頼（health → 作物一覧 → 植え付けを名前で探す・候補が複数なら確認 → 写真付きの栽培記録・収穫・日記）を試して比べる。使えればメインと `auxiliary`（`auxiliary.free_only: true` など）の両方を無料にする。無料モデルは回数制限と、何段階もの操作の誤りに注意 | 未着手 |
| 2026-10-10 | Hermes をメッセージアプリにつなぐ | gateway は起動しているがメッセージアプリは未接続（`No messaging platforms enabled.`）。スマホから写真付きで登録できるようにするのが外部 API の本来の目的 | 未着手 |
| 2026-10-10 | Hermes がスクリプトで結果を整形するたびに承認を求められるのを減らす | Hermes は `python3 -c` を危険なコマンドとして毎回確認する。SKILL.md に「応答の整形にスクリプトを使わない」等を足すか検討 | 未着手 |
| 2026-10-10 | アプリを Ubuntu（.24）へ移設する | 手順は [`api/migration-to-ubuntu.md`](api/migration-to-ubuntu.md)。Hermes が `pika3` で動いている点に注意（手順書 §6） | 未着手 |
