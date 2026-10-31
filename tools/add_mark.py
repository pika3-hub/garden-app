"""README の概要の絵（docs/images/overview.webp）の右下に、枠付きのマークを小さく重ねる。

マークは作者の GitHub のアイコンと同じキャラクター（画像はリポジトリに置いていない）。
Codex に描かせると形が変わるので、生成後に重ねている。

    uv run --no-project --with pillow python tools/add_mark.py <元の絵.png> <マーク.png> docs/images/overview.webp
"""
import sys
from PIL import Image, ImageDraw, ImageFilter

base_path, mark_path, out_path = sys.argv[1:4]
SIZE = 120      # マークの一辺（px、1536 幅の絵に対して）
BORDER = 5      # 枠の太さ
RADIUS = 18     # 角の丸み
MARGIN = 18     # 絵の端からの距離
BROWN = (92, 58, 30, 255)  # アイコンの輪郭に近い濃い茶色

base = Image.open(base_path).convert('RGBA')
mark = Image.open(mark_path).convert('RGBA').resize((SIZE, SIZE), Image.LANCZOS)

outer = SIZE + BORDER * 2
x = base.width - outer - MARGIN
y = base.height - outer - MARGIN

# うっすら影
shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle(
    (x + 3, y + 4, x + outer + 3, y + outer + 4), RADIUS + BORDER, fill=(0, 0, 0, 70))
base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(4)))

# 枠（角丸の茶色）
frame = Image.new('RGBA', base.size, (0, 0, 0, 0))
ImageDraw.Draw(frame).rounded_rectangle((x, y, x + outer, y + outer), RADIUS + BORDER, fill=BROWN)
base = Image.alpha_composite(base, frame)

# マーク（角丸で切り抜き）
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), RADIUS, fill=255)
base.paste(mark, (x + BORDER, y + BORDER), mask)

base.convert('RGB').save(out_path, 'WEBP', quality=82, method=6)
