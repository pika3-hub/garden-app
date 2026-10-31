# OpenAI の画像モデルでアイコンを作る

アプリのアイコン（`app/static/images/icon_*.webp`）と同じ絵柄の画像を、OpenAI の画像モデルで作る手順とノウハウ。2026-10-26 にナビの「Hermes」「設定」のアイコン（`icon_hermes.webp` / `icon_settings.webp`）を API の `gpt-image-2` で作った。

作り方は2つある。**既定は Codex**（2026-10-27 に検証して決めた）。

| | Codex（ChatGPT Plus の枠） | API（`gpt-image-2`） |
|---|---|---|
| 費用 | ChatGPT Plus の枠から引かれる（1枚で5時間枠の約2%）。別の課金なし | 1枚 $0.06 前後。前払いのクレジット |
| キー | 不要（ChatGPT でログイン済みの Codex） | `OPENAI_API_KEY`（期限付きで作るので切れたら作り直す） |
| 背景 | 最初から透明 | 透明にできず、マゼンタを抜く |
| 速さ | 1枚 約100秒 | 1枚 数十秒、まとめて作れる |
| 使う場面 | ふだん | Plus の枠が残り少ないとき（Hermes のふだんのモデルと同じ枠） |

画像を作るのはメイン PC の作業だけで、アプリ本体や本番のサーバーは OpenAI を使わない。

## Codex で作る（既定）

Codex のデスクトップアプリに CLI（`codex.exe`）が同梱されているので、別にインストールしない。フォルダ名のハッシュはアプリの更新で変わるので、毎回探す:

```powershell
$cx = (Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe" | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
& $cx login status   # Logged in using ChatGPT
```

1. 見本のアイコン（既定は料理・タスク・カレンダーの3枚）を PNG に変換して出力先の `refs/` に置く（WebP のまま渡せるかは未確認）
2. 指示を出力先の `prompt.txt` に書く。絵柄の文は `tools/make_icon.py` の `STYLE` と同じで、背景の文だけ透明にする:
   ```text
   Use the imagegen skill with the built-in image_gen tool (do not use the CLI fallback or any API key).
   The attached images are reference icons only (style references, not edit targets).
   Generate ONE new app menu icon in exactly the same art style as the reference icons:
   （STYLE の絵柄の部分）
   Background: genuinely transparent (alpha), not a painted checkerboard and not a solid color.
   Subject: <題材（英語）>
   After generating, copy the generated PNG into the current working directory as <名前>.png.
   ```
3. 実行する。`OPENAI_API_KEY` を外しておくと、誤って API（課金される）に切り替わらない:
   ```powershell
   $env:OPENAI_API_KEY = $null
   Get-Content <出力先>\prompt.txt -Raw | & $cx exec -C <出力先> --skip-git-repo-check -s workspace-write `
       -i <出力先>\refs\icon_cooking.png -i <出力先>\refs\icon_tasklist.png -i <出力先>\refs\icon_calendar.png -
   ```
   候補を複数作るときは、題材ごとに1回ずつ実行する（1回の指示で複数枚を頼む形は未検証）
4. できた PNG（1254×1254、透明背景）を出力先の `raw/` に置き、縮小と一覧だけ作る:
   ```powershell
   uv run --no-project --with pillow --with numpy python tools/make_icon.py --out <出力先> --cut-only --transparent
   ```
   `cut/` の WebP と `compare.png` の扱いは API のときと同じ（下の「作り方」）

- 元の画像は `~/.codex/generated_images/<スレッド>/` にも残る
- 物の部分の不透明度が 255 ではなく 250〜253 になっている（わずかに透ける）。`--transparent` は 240 以上を 255 にそろえる
- 使った枠は `~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl` の最後の `rate_limits`（`primary` が5時間枠、`secondary` が週の枠の使用率）で分かる

## Codex で README の挿絵を作る（横長・文字入り）

2026-10-31 に README の概要の絵（`docs/images/overview.webp`）を、アイコンと同じ Codex の手順で作った。指示文は `docs/images/overview.prompt.txt`（見本はメニューアイコンの作物・写真・収穫・Hermes の4枚を PNG にして `-i` で渡した）。

- **横長にできる**: 指示に「landscape 3:2, 1536x1024」と書けば 1536×1024 で出る（背景は透明にせず、薄いクリーム色を指示）
- **日本語の文字もきれいに入る**: 「写真を撮る」などの短い言葉を4つ、`exactly these short Japanese labels` と書いて番号付きで並べたら、3枚とも誤字・崩れなし。言葉の無い版も作って比べたが、AI のお手伝い役（ロボット）が何者かは言葉がないと伝わりにくく、言葉ありを採用した
- **構図は場所まで指示する**: 最初の版（左から右へ4場面）は下の 3 分の 1 が畑の風景だけになった。「4場面を時計回り（左上・右上・右下・左下）、真ん中に畝、下の地面は高さの1割まで」と書いたら、一周する形で場面が大きくなった
- 1枚 約2〜3%（5時間枠）。3枚で 8% だった
- 右下の枠付きのマーク（作者の GitHub のアイコンと同じキャラクター）は Codex に描かせず、生成後に `tools/add_mark.py`（Pillow）で重ねた。Codex に渡すと描き直されて形が変わるため。マークの画像はリポジトリに置いていない
- 2MB の PNG は WebP（品質 82）にして約 190KB にした（`tools/add_mark.py` が WebP で書き出す）
- 「言葉なし」と頼むと、Codex が指示を自分で書き直して（`*.prompt.txt` に残る）文字を徹底して消した

## 絵柄（既存アイコンの特徴）

- ゲームのアイテム風のぷっくりした立体感とつや
- 太めの濃い茶色の輪郭
- 暖かい色（オレンジ・木目・クリーム）に、小さな緑の葉を添える
- 透明背景、正方形に収まる1つの物、文字なし
- 100×100 の WebP

## API で作る

### API キーの準備

1. https://platform.openai.com にログイン（ChatGPT と同じアカウントでよいが、API の請求は ChatGPT Plus とは別）
2. Settings → Billing で前払いのクレジットを入れる（$5 程度で足りる。自動チャージは切る）
3. Settings → Limits で月の使用額の上限を設定する
4. API keys → Create new secret key。権限は可能なら Restricted で画像だけ、期限も付けておく（期限が切れていたら作り直す）
5. PowerShell で、キーがコマンドの履歴に残らない形でユーザー環境変数に設定する（貼り付けても画面には出ない）:
   ```powershell
   $k = Read-Host 'OpenAI API key' -AsSecureString; [Environment]::SetEnvironmentVariable('OPENAI_API_KEY', [Net.NetworkCredential]::new('', $k).Password, 'User'); Remove-Variable k
   ```
6. **VS Code を完全に終了して起動し直す**（Claude Code のコマンドは VS Code の起動時の環境変数を引き継ぐ）
7. 確認（値は出さない）: `powershell -NoProfile -c '[bool]$env:OPENAI_API_KEY'` が `True`、`GET https://api.openai.com/v1/models/gpt-image-2`（`Authorization: Bearer`）が 200。課金されない

キーの値はチャットに貼らない・表示しない・ファイルに書かない。

### 作り方

`tools/make_icon.py` を使う。題材は英語で、`名前="題材"` の形で並べる。出力先はリポジトリの外（Claude Code ならスクラッチ領域）にする。

```powershell
uv run --no-project --with openai --with pillow --with numpy python tools/make_icon.py --out <出力先> `
    hermes_a="a speech bubble with three dots inside, and a small green sprout with two leaves growing from the top edge" `
    settings_b="a chunky orange gear with a small garden trowel with a wooden handle crossed in front of it, and a couple of small green leaves"
```

- 出力先の `raw/` に生成した 1024×1024 の PNG、`cut/` に背景を透明にした 100×100 の WebP、`compare.png` に見本と候補を白・暗い背景の2段に並べた一覧ができる
- `compare.png` を見て候補を選んでもらい、`cut/` の WebP を `app/static/images/icon_{名前}.webp` にコピーする
- 切り抜きのしかたを変えたときは、`--cut-only` で生成し直さずに作り直せる（費用なし）
- 見本は既定で料理・タスク・カレンダーの3枚（`--samples` で変えられる）。`images/edits` に WebP を直接渡さず、PNG に変換して渡している
- 生成の前に枚数と費用の見込みをユーザーに伝える。候補は題材を変えて数枚作り、ユーザーに選んでもらう

## ノウハウ・落とし穴

- **`gpt-image-2` は透明背景（`background="transparent"`）を受け付けない**（`400 Transparent background is not supported for this model.`。このエラーは課金されない）。代わりに、プロンプトで「平らな単色のマゼンタ（#FF00FF）の背景、物にはマゼンタやピンクを使わない」と指示し、あとからマゼンタを透明にしている
  - 白い背景だと、クリーム色の部分まで抜けてしまう。緑の背景は葉と重なる。マゼンタなら既存の絵柄と重ならない
  - 実際の背景は (240, 10, 240) 前後で、真のマゼンタからは少しずれる。キー色からの距離で透明度を決めている（距離 60 未満は透明、150 以上は不透明、その間は半透明）
  - 縁の半透明の部分はマゼンタが混ざるので、混ざった分を取り除いている（取らないと暗い背景で縁がピンクににじむ）
- **外周からの塗りつぶしで背景を決めると、歯車の穴やサンダルの輪の内側のような、囲まれた背景が残る。** 色だけで判定している
- **PIL で `Image.fromarray()` した画像に `ImageDraw.floodfill()` をしても、書き込みが反映されないことがある**（numpy 配列とメモリを共有しているため）。`.copy()` してから使う
- 小さく表示したときの見え方で選ぶ。ナビでは 1.3em 程度になるので、込み入った絵（道具を2つ重ねるなど）や細い葉は目立たなくなる。`compare.png` の 100px で判断する
- 「Hermes」のような名前そのものを題材にすると（羽付きサンダル）、名前を知らない人には何の画面か分かりにくい

## 費用（API）

- 1024×1024・`quality: medium` で、1枚あたり出力 1756 トークン、入力（見本3枚と文章）約 320 トークン。公式の目安では約 $0.053 + 入力分で、**1枚 $0.06 前後**
- 2026-10-26 の5枚で約 $0.3 の見込み

## 組み込み

- ナビは `app/templates/base.html` の `<img src="{{ url_for('static', filename='images/icon_xxx.webp') }}" alt="" class="icon-img icon-img-lg">`
- 画面の見出しは同じ `icon-img icon-img-lg`、カードの見出し（`h6`）は `icon-img`
- 画像を足したら、画像の一覧 [`image-catalog.html`](image-catalog.html) の該当する節（アイコンなら「メニューアイコン画像」）にも足す
