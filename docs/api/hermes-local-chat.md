# Telegram を使わずに Hermes と話す（LAN 内のチャット）の調査

2026-10-14 に調べて方針を決めた段階のメモ。**まだ構築していない**。まとまった時間が取れたら、ここから設計・構築に進む。

## 目的

今はスマホから Hermes への依頼が Telegram（インターネット上の Telegram 社のサーバー）を通っている。これを、**すでにあるアプリの機能と Hermes Agent 以外は自宅の LAN の中だけ**で済む形に置き換えたい。OpenRouter（Hermes のモデル）と Anthropic（AI メモ下書き）へのインターネット接続はそのまま使ってよい。

- 外出先から使えなくなるのは構わない（LAN 内だけで使う）
- スマホへのプッシュ通知は無くてよい（iPhone のプッシュ通知は Apple のサーバーを通るため、完全ローカルにすると通知は使えない）
- SSH でサーバーに入ってターミナルの `hermes` を使う方法は、スマホでの操作性から採用しない

## 今の構成でデータがどこへ出るか

| 経路 | どこまで出るか | 出るもの |
|---|---|---|
| Web 画面（ブラウザ → 5000 番） | LAN 内だけ | なし |
| 外部 API（Hermes → 5001 番） | サーバーの中だけ（127.0.0.1） | なし |
| Telegram（スマホ ↔ Hermes） | Telegram のサーバー経由 | 依頼の文面、送った写真、Hermes の返信 |
| Hermes のモデル | OpenRouter 経由でモデルの提供元へ | 会話全体（スキル、API の結果の JSON、診断に使う写真） |
| AI メモ下書き | Anthropic の Claude API へ | 作物名・地域などの入力、Web 検索の依頼 |

ほかに、OGP の取得（そのサイトへ）と更新時の `git pull`（GitHub へ）がある。

Telegram の仕組み: スマホの Telegram アプリと、サーバーの gateway（`hermes-gateway.service`）は直接つながっていない。どちらも Telegram のサーバーに外向きに接続する。gateway はロングポーリング（`getUpdates`）で新しいメッセージを取りに行き、返信は `sendMessage` で送る。Telegram 側からサーバーの様子を見に来ることはない。

## 調べた選択肢（Hermes v0.21.6 で確認）

Hermes の対応プラットフォームのうち、LAN 内で完結できるのは次の2つ。

### API サーバー＋Open WebUI（不採用）

- Hermes には OpenAI 互換の API サーバーがある（`~/.hermes/.env` に `API_SERVER_ENABLED=true` と `API_SERVER_KEY`。既定は `127.0.0.1:8642`）。Open WebUI（自前で動かすブラウザのチャット画面）からつなぐ手順が公式にある
- **チャットで送った写真をアプリに登録できない**。`gateway/platforms/api_server.py`（465〜537 行目付近）は画像を `image_url` のままモデルに渡すだけで、ファイルに保存しない（`cache_image` を呼ばない）。Hermes は写真を見て診断はできても、API にアップロードするファイルが手元に無い
- 回避するには、写真を先に Web 画面の写真プールに上げ、Open WebUI で「写真プールの最新3枚を〜」と頼む。写真と依頼の画面が分かれる

### Matrix サーバー＋Element（採用予定）

- Matrix はチャットの規格。Matrix サーバー（ホームサーバー）が Telegram 社のサーバーの役を、Element アプリが Telegram アプリの役をする。Hermes は gateway の Matrix 用アダプター（`plugins/platforms/matrix/adapter.py`）で Bot として接続する
- **写真は Telegram と同じくファイルに保存される**（`adapter.py` 2298〜2310 行目付近の `cache_image_from_bytes_async`）。写真付きで頼む → Hermes が API にアップロード、の今の流れがそのまま使える見込み
- 公式に、自前のサーバー（Synapse、Conduit の系統など）で使えると書かれている
- サーバーの Hermes には Matrix の部品（`mautrix`）がまだ入っていない

## 決めたこと

- **Matrix＋Element で進める**。Matrix サーバーは今の Ubuntu サーバー（garden-app と Hermes がある機械）に同居させる。置き場所は `/opt/garden-app` と分け、別のユーザーで動かす（Hermes の実行ユーザーが `/opt/garden-app` に触れない今の分け方を崩さない）
- **フェデレーション（他の Matrix サーバーとの連携）は切る**。LAN からだけ ufw で許可する
- **HTTPS は使う**。LAN 内用の証明書（mkcert など）を作り、発行元を iPhone・iPad に一度登録する。Wi-Fi 上のパスワード・アクセストークン・写真を守れ、iOS の HTTP 制限の心配も無くなる。作った証明書は Web 画面の HTTPS 化にも使い回せる
- **E2EE（エンドツーエンド暗号化）は第2段階で試す**。まず E2EE なしで写真の登録まで動かし、その後、暗号化ありの新しい部屋を作って試す。運用が面倒なら暗号化なしの部屋に戻る
  - E2EE は途中のサーバーに中身を読ませない仕組み。サーバーが自分のもので外に出ず、相手の Bot も同じサーバーにいるので、この構成での効果はほとんどない
  - 運用のリスク: 鍵の保管場所（crypto store）が壊れる・消えると Bot がメッセージを読めなくなる（黙って無視しやすい）、時計がずれるとメッセージが黙って捨てられる、DB を見ても中身を調べられない、部品（`mautrix` の暗号化対応版と `libolm`）が増える
- Telegram はしばらく並行して残す

## 構築前に決める・確かめること

- Matrix サーバーのソフト（軽量な Conduit の系統が候補。今も保守されている版を選ぶ）
- Hermes の仮想環境の場所と、`mautrix` の入れ方（`./venv/bin/python` は無かった）
- Element は Bot との1対1のチャットを既定で暗号化ありで作る。第1段階では、部屋を作るときに暗号化をオフにする（後からオフにはできない）
- Element（iPhone）が iPhone の写真を JPEG で送るか。HEIC のままだと Telegram の「ファイル」と同じく、gateway の形式チェックで断られる見込み
- 公式の Matrix のページに `/new` の記載が無い（`/resume`・`/discardsession` などはある）。セッションの区切り方を確かめる
- Hermes を更新する（`hermes update`）かどうか。調べたのは v0.21.6

## 参考

- [API Server（Hermes Agent 公式）](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
- [Open WebUI（Hermes Agent 公式）](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/open-webui)
- [Matrix（Hermes Agent 公式）](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/matrix)
