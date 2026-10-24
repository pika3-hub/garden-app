# Hermes のモデル（ChatGPT の枠＋予備に OpenRouter）

2026-10-24 から、サーバーの Hermes は **ChatGPT Plus の枠（プロバイダー `openai-codex`）の `gpt-6-luna`** で動いている。Codex が失敗したとき（上限の 429、5xx、認証エラーなど）だけ、それまでの **OpenRouter の `anthropic/claude-haiku-5.5`** に切り替わる（予備）。それより前は OpenRouter の Haiku だけだった。

- 料金: ふだんは ChatGPT Plus の月額の中。OpenAI API の従量課金ではない。ChatGPT の「使用状況と制限」の「エージェント機能の利用上限」（5時間・週間）から引かれ、自分の ChatGPT・Codex の利用と同じ枠を使う。2026-10-24 の検証では、短い質問 約10回＋API を使う依頼 2回で 5時間の枠が 1% 減った
- 予備に切り替わると OpenRouter の従量課金になる。切り替えは依頼（ターン）ごとで、次の依頼ではまた Codex から試す（Codex が上限の戻る時刻を返したときは、その時刻まで予備を使い続ける）
- 公式の説明: [providers（OpenAI Codex）](https://hermes-agent.nousresearch.com/docs/integrations/providers)、[fallback providers](https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers)

## 設定

`~/.hermes/config.yaml`（Hermes の実行ユーザー）:

```yaml
model:
  default: "gpt-6-luna"
  provider: "openai-codex"
  # base_url: "https://openrouter.ai/api/v1"   ← OpenRouter のときの行。Codex では書かない（コメントにして残している）

fallback_providers:          # ファイルの最後（トップレベル）
  - provider: openrouter
    model: anthropic/claude-haiku-5.5
```

- `hermes fallback list` で、Primary と Fallback chain の読み取り結果を確かめられる
- 書き換えたら `systemctl --user restart hermes-gateway.service`。gateway のログ（`~/.hermes/logs/gateway.log`）に `Model context warmed: gpt-6-luna` が出れば反映されている
- 予備の OpenRouter のキーは `~/.hermes/.env` の `OPENROUTER_API_KEY` のまま。`model.base_url` をコメントにしても、`--provider openrouter` で OpenRouter に届く（確認済み）

## ログイン（ChatGPT アカウント）

```bash
hermes auth add openai-codex
```

- 既定はデバイスコード方式。表示された `https://auth.openai.com/codex/device` をスマホなどで開いてコードを入れる。サーバーで SSH のトンネルを張る必要はない
- 認証情報は `~/.hermes/auth.json`。Codex CLI や VS Code のログインとは別のセッション
- 公式の説明にある「OpenSSL 3.5 以降でデバイスログインが失敗することがある」は、サーバー（OpenSSL 3.5.5）では起きなかった
- 更新が失敗し続けると Hermes はトークンを無効扱いにする。そのときは同じコマンドでログインし直す
- ChatGPT 側の画面: 2026-10-24 時点では、ログインの許可画面に「Use your ChatGPT plan」の文言も、「使用状況と制限」にアプリごとの上限の欄も見つからなかった（OpenAI の Sign in with ChatGPT の対応一覧には Hermes Agent が載っている）。枠から引かれていることは % の減りで確かめた

## 使えるモデル（ChatGPT Plus、2026-10-24）

| 使えた | 断られた（`HTTP 400: The '…' model is not supported when using Codex with a ChatGPT account`） |
|---|---|
| `gpt-6-sol`、`gpt-6-luna`、`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna` | `gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini` |

- Hermes の既定の候補一覧（`hermes_cli/codex_models.py` の `DEFAULT_CODEX_MODELS`）は契約に関係ない一覧で、ChatGPT アカウントでは断られるものも入っている。確かめるときは実際に送る:

```bash
for m in gpt-6-sol gpt-6-luna gpt-5.6-sol; do echo "== $m"; hermes chat --provider openai-codex -m "$m" -Q --oneshot -q "1+1は？数字だけで答えて" 2>&1 | grep -v '^session_id' | head -3; done
```

- `gpt-6-luna` を選んだ理由: 菜園アプリのスキルで、読み取り（植え付けの一覧）・写真の診断（`/image`）・書き込み（日記の登録と関連付け）がすべて正しくできた。軽いモデルなので枠の減りが少ないと見込んでいる（名前からの推測。重いモデルとの比較はしていない）

## gateway を変えずに試す

`hermes chat` の `--provider` と `-m` で、その1回だけ別のモデルで動かせる（`config.yaml` は変わらない）。菜園アプリの API を使うときは、先に接続情報を読み込む:

```bash
set -a; . ~/.config/garden-api.env; set +a
hermes chat --provider openai-codex -m gpt-6-luna -s garden-app -Q --oneshot -q "菜園アプリのAPIで、栽培中の植え付けを3件、作物（品種）名と場所で一覧して。データは変更しないで。"
```

## 戻すとき（OpenRouter の Haiku だけに戻す）

`config.yaml` の `model:` を `default: "anthropic/claude-haiku-5.5"` / `provider: "openrouter"` / `base_url: "https://openrouter.ai/api/v1"` に戻し、`fallback_providers:` の節を消して gateway を再起動する。切り替え前の設定ファイルは `~/.hermes/config.yaml.bak-before-codex` に退避してある（その後に別の設定を変えていれば、丸ごと戻すとそれも消えるので、`diff` を見てから戻す）。ChatGPT との接続をやめるときは、ChatGPT の 設定 > セキュリティ からも外す。
