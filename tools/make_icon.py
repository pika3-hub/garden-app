"""アプリのアイコン（app/static/images/icon_*.webp）と同じ絵柄の画像を OpenAI の画像モデルで作る。

既存のアイコンを見本として images/edits に渡し、マゼンタ単色の背景で描かせてから
背景を透明にし、100×100 の WebP と見比べ用の一覧（compare.png）を出力先に作る。
キーは環境変数 OPENAI_API_KEY から読む（表示しない）。手順とノウハウは ../garden-app-private/docs/image-generation.md。

使い方（メイン PC、出力先はリポジトリの外に）:
    uv run --no-project --with openai --with pillow --with numpy python tools/make_icon.py \\
        --out <出力先> hermes_a="a speech bubble with three dots inside, ..." settings_a="a gear ..."
    # 生成し直さずに切り抜きと一覧だけ作り直す
    uv run --no-project --with pillow --with numpy python tools/make_icon.py --out <出力先> --cut-only
    # Codex（ChatGPT の枠）で作った透明背景の PNG を raw/ に置いて、縮小と一覧だけ作る
    uv run --no-project --with pillow --with numpy python tools/make_icon.py --out <出力先> --cut-only --transparent
    # 作物のアイコン（crop_icons/ の 84×84 の PNG）として縮小する
    uv run --no-project --with pillow --with numpy python tools/make_icon.py --out <出力先> --cut-only --transparent --crop
"""
import argparse
import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image

IMAGES = Path(__file__).resolve().parent.parent / 'app' / 'static' / 'images'
DEFAULT_SAMPLES = ['icon_cooking.webp', 'icon_tasklist.webp', 'icon_calendar.webp']

# gpt-image-2 は background='transparent' を受け付けない（400）ので、キー色の背景で描かせて抜く
KEY = np.array([255, 0, 255], dtype=np.float32)
T0, T1 = 60.0, 150.0  # キー色からの距離: T0 未満は完全に透明、T1 以上は不透明
SIZE = 100
MARGIN = 4  # 既存アイコンと同じくらいの余白（100px 中）
# 作物のアイコン（crop_icons/）は 84×84 の PNG で、物は 72px 前後に描かれている
CROP_SAMPLES = ['crop_icons/icon_001.png', 'crop_icons/icon_008.png', 'crop_icons/icon_066.png', 'crop_icons/icon_071.png']
CROP_SIZE = 84
CROP_MARGIN = 6
OPAQUE = 240  # --transparent: この不透明度以上は完全に不透明にする

STYLE = (
    'Create a new app menu icon in exactly the same art style as the reference icons: '
    'cute game-item style, puffy 3D shape with glossy highlights, thick dark-brown outline, '
    'warm colors (orange, wood, cream) with a few small fresh green leaves as an accent '
    '(this is a home vegetable garden app). '
    'A single object centered and fitting inside a square, no text, no letters, no shadow on the ground. '
    'The object alone on a perfectly flat, solid, uniform pure magenta background (#FF00FF), '
    'with no gradient, no texture and no other objects; do not use magenta or pink in the object itself.'
)


def sample_files(names):
    files = []
    for name in names:
        buf = io.BytesIO()
        Image.open(IMAGES / name).convert('RGBA').save(buf, 'PNG')
        files.append((Path(name).stem + '.png', buf.getvalue(), 'image/png'))
    return files


def generate(out, subjects, samples, model, quality):
    from openai import OpenAI

    client = OpenAI()
    for name, subject in subjects.items():
        result = client.images.edit(
            model=model,
            image=sample_files(samples),
            prompt=f'{STYLE}\nSubject: {subject}',
            output_format='png',
            size='1024x1024',
            quality=quality,
        )
        path = out / 'raw' / f'{name}.png'
        path.write_bytes(base64.b64decode(result.data[0].b64_json))
        print(f'{name}: {path} usage={result.usage}')


def cutout(path):
    rgb = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    dist = np.linalg.norm(rgb - KEY, axis=2)
    # 外周からの塗りつぶしにはしない（歯車の穴のような囲まれた背景も消すため）
    alpha = np.clip((dist - T0) / (T1 - T0), 0, 1)

    # 縁の半透明部分からマゼンタの混ざりを取り除く
    a = np.maximum(alpha, 1e-3)[..., None]
    color = np.clip((rgb - (1 - a) * KEY) / a, 0, 255)
    return Image.fromarray(np.dstack([color, alpha * 255]).astype(np.uint8), 'RGBA')


def from_transparent(path):
    """透明背景で描かれた画像（Codex の image_gen）を使う。物の部分がわずかに透けている（250〜253）のでそろえる"""
    rgba = np.array(Image.open(path).convert('RGBA'))
    rgba[..., 3] = np.where(rgba[..., 3] >= OPAQUE, 255, rgba[..., 3])
    return Image.fromarray(rgba, 'RGBA')


def fit(img, size, margin):
    """物の範囲で切り出し、余白を付けて size×size に収める"""
    img = img.crop(img.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox())
    scale = (size - margin * 2) / max(img.size)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def compare_sheet(icons, samples, size):
    """見本と候補を白・暗い背景の2段に並べる（透明の抜け残りを見つけやすい）"""
    tiles = [Image.open(IMAGES / n).convert('RGBA') for n in samples] + icons
    pad = 10
    rows = []
    for bg in [(255, 255, 255, 255), (33, 37, 41, 255)]:
        row = Image.new('RGBA', (len(tiles) * (size + pad) + pad, size + pad * 2), bg)
        for i, t in enumerate(tiles):
            row.alpha_composite(t, (pad + i * (size + pad), pad))
        rows.append(row)
    sheet = Image.new('RGBA', (rows[0].width, rows[0].height * 2))
    sheet.paste(rows[0], (0, 0))
    sheet.paste(rows[1], (0, rows[0].height))
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('subjects', nargs='*', metavar='名前="題材（英語）"')
    parser.add_argument('--out', required=True, type=Path, help='出力先（リポジトリの外）')
    parser.add_argument('--samples', nargs='+', help='見本にする app/static/images のファイル（既定はメニューのアイコン3枚、--crop なら作物のアイコン4枚）')
    parser.add_argument('--model', default='gpt-image-2')
    parser.add_argument('--quality', default='medium', choices=['low', 'medium', 'high'])
    parser.add_argument('--cut-only', action='store_true', help='生成せず raw/ の画像から作り直す')
    parser.add_argument('--transparent', action='store_true',
                        help='raw/ の画像は透明背景（Codex で作った）なので、マゼンタを抜かない。--cut-only と使う')
    parser.add_argument('--crop', action='store_true', help='作物のアイコン（crop_icons/ の 84×84 の PNG）として作る')
    args = parser.parse_args()
    if args.transparent and not args.cut_only:
        parser.error('--transparent は --cut-only と一緒に使う（API での生成はマゼンタの背景になる）')
    if args.crop and not args.cut_only:
        parser.error('--crop は --cut-only と一緒に使う（API での生成の指示はメニューのアイコンの絵柄）')
    if args.samples is None:
        args.samples = CROP_SAMPLES if args.crop else DEFAULT_SAMPLES
    size, margin, ext = (CROP_SIZE, CROP_MARGIN, 'png') if args.crop else (SIZE, MARGIN, 'webp')

    (args.out / 'raw').mkdir(parents=True, exist_ok=True)
    (args.out / 'cut').mkdir(exist_ok=True)
    if not args.cut_only:
        subjects = dict(s.split('=', 1) for s in args.subjects)
        if not subjects:
            parser.error('題材を 名前="..." の形で1つ以上指定する')
        generate(args.out, subjects, args.samples, args.model, args.quality)

    icons = []
    for path in sorted((args.out / 'raw').glob('*.png')):
        icon = fit(from_transparent(path) if args.transparent else cutout(path), size, margin)
        if args.crop:
            icon.save(args.out / 'cut' / f'{path.stem}.png', 'PNG', optimize=True)
        else:
            icon.save(args.out / 'cut' / f'{path.stem}.webp', 'WEBP', lossless=True)
        icons.append(icon)
    compare_sheet(icons, args.samples, size).save(args.out / 'compare.png')
    print(f'cut: {args.out / "cut"}  compare: {args.out / "compare.png"}')


if __name__ == '__main__':
    main()
