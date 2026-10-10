# Hermes と Telegram の接続

スマホ（iPhone の Telegram）から Hermes に依頼し、写真付きで菜園データを登録するための設定。2026-10-10 に .24 で接続した。

## 構成

- ボットは BotFather で作成（`/setjoingroups` を `Disable` にして、グループに追加できないようにしている）
- .24 の `~/.hermes/.env`（権限 600）に `TELEGRAM_BOT_TOKEN` と `TELEGRAM_ALLOWED_USERS`（自分の数値ユーザー ID。`@userinfobot` で確認）を追記。Hermes はコマンドを実行できるため、`TELEGRAM_ALLOWED_USERS` は必須（`GATEWAY_ALLOW_ALL_USERS` は使わない）
- gateway（`hermes-gateway.service`）を再起動すると `.env` を読んで接続する。ログに `✓ telegram connected` と `Connected to Telegram (polling mode)` が出れば成功
- ロングポーリング（.24 から Telegram に取りに行く）なので、.24 をインターネットに公開する必要はない。LINE は公開 HTTPS の Webhook が必要なため採用しなかった
- ボットとのチャットで `/sethome` を送り、ホームチャンネル（定期実行の結果などの送り先）にしている

トークンを入力するときは、画面と履歴に残さない:

```bash
read -rsp 'Bot token: ' T; echo; read -rp 'User ID: ' U
printf '\n# Telegram (garden bot)\nTELEGRAM_BOT_TOKEN=%s\nTELEGRAM_ALLOWED_USERS=%s\n' "$T" "$U" >> ~/.hermes/.env; unset T U
```

## 使うときの注意

- **会話（セッション）は毎回まるごとモデルに送られる**。モデルは前の会話を覚えていないため、Hermes はメッセージのたびに、スキルと**そのセッションのそれまでの会話全体**（curl の結果の JSON も含む）を送り直す。使うほど1回あたりの入力トークン（料金）が増え、前の話題に引きずられることもある。長くなると Hermes が自動で要約する（補助モデルを使う）
- **セッションは自動ではリセットされない**（時間がたっても日付が変わっても続く）。区切りごと（その日の登録が終わったら、話題を変えるときなど）に **`/new`** を送る。必要な情報は毎回 API から取り直すので、`/new` しても困らない。Telegram の画面の履歴は `/new` 後も残るが、Hermes のセッションとは別物（画面に見えていても、`/new` より前の内容はモデルに送られない）
- 料金は OpenRouter の Activity 画面で、リクエストごとの入力トークン数として確認できる

## Hermes の自己改善（SKILL.md と USER.md の書き換え）

Hermes は会話の後に裏で振り返り（self-improvement review）を行い、Telegram に `Self-improvement review: Skill 'garden-app' patched` / `User profile updated` と通知する。

- **`Skill 'garden-app' patched`**: .24 の `~/.hermes/skills/garden-app/SKILL.md` を Hermes が直接書き換えている。履歴やバックアップは残らない。2026-10-10 の試用では11か所追記され、大半は正しかったが、誤った説明（`q` の検索対象）や遠回りの手順（品種の作成と写真を2回に分ける）も含まれていた。レビューしてリポジトリに取り込んだ
- **`User profile updated`**: `~/.hermes/memories/USER.md`（上限 1,375 文字）に追記している。毎回のセッションの最初にシステムプロンプトへ入る。「『昨日』は 2026-10-09 として扱う」のような、その日にしか正しくない内容が入ることがあるので、ときどき中身を確認する
- **SKILL.md を .24 に送る前に、必ず .24 の版を取ってきて比べる**（そのまま送ると Hermes の追記が消える）:
  ```powershell
  scp pika3@192.168.11.24:~/.hermes/skills/garden-app/SKILL.md "$env:TEMP\SKILL.24.md"
  ```
  よい追記はリポジトリの `docs/api/hermes-skill/SKILL.md` に取り込み、それから送る
- 書き換えを承認制にするには、Telegram で `/skills approval on`（記憶は `/memory approval on`）。保留中の変更は `/skills diff <id>` で確認できる。振り返り自体を止めるのは `auxiliary.background_review.enabled: false`（`~/.hermes/config.yaml`）
- **gateway が止まっている間に送ったメッセージは捨てられる**（起動時に `drop_pending_on_cold_boot`）。返事がなければ送り直す
- **写真は「写真」として送る**。Telegram が JPEG に変換するが、960×1280px 程度に縮小され、EXIF（撮影日時）が消える。そのため写真プールに撮影日時が表示されない。日付は依頼の文面か今日の日付で決まるので、撮ってすぐ送るなら困らない。前に撮った写真は「9/20 に撮った」のように日付を書く
- **「ファイル」として送ると、iPhone の写真は HEIC のまま届く**。API は HEIC を 415 にする（Hermes は写真として送り直すよう案内する）。HEIC 対応は Ubuntu への移設後に行う予定（[`../wishlist.md`](../wishlist.md)）。メイン PC（Windows）では、HEIC を読むライブラリ `pillow-heif` の DLL が Smart App Control に止められるため対応できない
