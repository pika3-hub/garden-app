# OpenAI の画像モデルでアイコンを作る

アプリのアイコン（`app/static/images/icon_*.webp`）と同じ絵柄の画像を、OpenAI の画像モデル（`gpt-image-2`）で作る手順とノウハウ。2026-10-26 にナビの「Hermes」「設定」のアイコン（`icon_hermes.webp` / `icon_settings.webp`）をこの方法で作った。

画像を作るのはメイン PC の作業だけで、アプリ本体や本番のサーバーは OpenAI を使わない。

## 絵柄（既存アイコンの特徴）

- ゲームのアイテム風のぷっくりした立体感とつや
- 太めの濃い茶色の輪郭
- 暖かい色（オレンジ・木目・クリーム）に、小さな緑の葉を添える
- 透明背景、正方形に収まる1つの物、文字なし
- 100×100 の WebP

## API キーの準備

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

## 作り方

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

## 費用

- 1024×1024・`quality: medium` で、1枚あたり出力 1756 トークン、入力（見本3枚と文章）約 320 トークン。公式の目安では約 $0.053 + 入力分で、**1枚 $0.06 前後**
- 2026-10-26 の5枚で約 $0.3 の見込み

## 組み込み

- ナビは `app/templates/base.html` の `<img src="{{ url_for('static', filename='images/icon_xxx.webp') }}" alt="" class="icon-img icon-img-lg">`
- 画面の見出しは同じ `icon-img icon-img-lg`、カードの見出し（`h6`）は `icon-img`
