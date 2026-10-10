from PIL import Image, ImageDraw, ImageFilter
import math
from pathlib import Path

W, H = 1000, 260
STEP, PIXEL = 16, 13
FRAMES_PER_WORD = 240
FRAME_MS = 50
WORDS = ["IAGO LIMA", "IFCE", "BOAMA"]
GLYPHS = {
    "A":["01110","10001","10001","11111","10001"],
    "B":["11110","10001","11110","10001","11110"],
    "C":["01111","10000","10000","10000","01111"],
    "E":["11111","10000","11110","10000","11111"],
    "F":["11111","10000","11110","10000","10000"],
    "G":["01111","10000","10111","10001","01111"],
    "I":["11111","00100","00100","00100","11111"],
    "L":["10000","10000","10000","10000","11111"],
    "M":["10001","11011","10101","10001","10001"],
    "O":["01110","10001","10001","10001","01110"],
}
BG = (5, 8, 22)
PIXEL_COLOR = (56, 189, 248)
PIXEL_EDGE = (125, 211, 252)
NEON = (34, 211, 238)

def build_word(word):
    cursor = 0
    letters = []
    pixels = []
    for ch in word:
        if ch == " ":
            cursor += 2
            continue
        pts = []
        for y, row in enumerate(GLYPHS[ch]):
            for x, bit in enumerate(row):
                if bit == "1":
                    pts.append((cursor + x, y))
        letters.append(pts)
        pixels.extend((cursor+x, y) for y, row in enumerate(GLYPHS[ch]) for x, bit in enumerate(row) if bit == "1")
        cursor += 6

    # Center the pixel-art word and map every grid cell to image coordinates.
    grid_width = cursor - 1
    offset_x = (W - grid_width * STEP) // 2
    offset_y = 48
    def center(gx, gy):
        return (offset_x + gx*STEP + PIXEL//2, offset_y + gy*STEP + PIXEL//2)

    route = []
    target_indices = {}
    seen = set()
    def push(gx, gy):
        if not route or route[-1] != (gx, gy):
            route.append((gx, gy))

    # Trace each letter completely, then move to the next letter.
    for letter in letters:
        seq = []
        for y in range(5):
            row = sorted((p for p in letter if p[1] == y), key=lambda p:p[0], reverse=bool(y % 2))
            seq.extend(row)
        for target in seq:
            if target in seen:
                continue
            if not route:
                push(*target)
            else:
                gx, gy = route[-1]
                tx, ty = target
                while gy != ty:
                    gy += 1 if ty > gy else -1
                    push(gx, gy)
                while gx != tx:
                    gx += 1 if tx > gx else -1
                    push(gx, gy)
            target_indices[target] = len(route)-1
            seen.add(target)

    # Precompute a soft neon glow for the pixel squares.
    glow_layer = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow_layer)
    for gx, gy in pixels:
        x = offset_x + gx*STEP
        y = offset_y + gy*STEP
        gd.rounded_rectangle((x-2,y-2,x+PIXEL+2,y+PIXEL+2), radius=3, fill=(*NEON,90))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(5))
    return route, target_indices, pixels, offset_x, offset_y, glow_layer

def draw_frame(word_data, progress):
    route, target_indices, pixels, offset_x, offset_y, glow_layer = word_data
    frame = Image.new("RGB", (W,H), BG)
    d = ImageDraw.Draw(frame)
    # Subtle background grid and border.
    for x in range(0,W,22):
        d.line((x,0,x,H), fill=(13,30,51), width=1)
    for y in range(0,H,22):
        d.line((0,y,W,y), fill=(13,30,51), width=1)
    d.rounded_rectangle((1,1,W-2,H-2), radius=17, outline=(29,78,216), width=1)

    head_dist = progress * (len(route)-1)
    # The word stays unchanged until the head reaches a pixel; then only that pixel disappears.
    for gx, gy in pixels:
        if head_dist < target_indices[(gx,gy)]:
            x = offset_x + gx*STEP
            y = offset_y + gy*STEP
            d.rounded_rectangle((x,y,x+PIXEL,y+PIXEL), radius=1, fill=PIXEL_COLOR, outline=PIXEL_EDGE, width=1)

    frame = Image.alpha_composite(frame.convert("RGBA"), glow_layer)
    # Remove the glow only around pixels already collected, preserving the background grid.
    d = ImageDraw.Draw(frame)
    for gx, gy in pixels:
        if head_dist >= target_indices[(gx,gy)]:
            x = offset_x + gx*STEP
            y = offset_y + gy*STEP
            d.rounded_rectangle((x-2,y-2,x+PIXEL+2,y+PIXEL+2), radius=3, fill=BG)

    def point_at(distance):
        distance = max(0.0, min(distance, len(route)-1))
        i = int(distance)
        frac = distance-i
        a = route[i]
        b = route[min(i+1,len(route)-1)]
        ax, ay = offset_x + a[0]*STEP + PIXEL//2, offset_y + a[1]*STEP + PIXEL//2
        bx, by = offset_x + b[0]*STEP + PIXEL//2, offset_y + b[1]*STEP + PIXEL//2
        return (ax+(bx-ax)*frac, ay+(by-ay)*frac)

    # Tail first, largest head last: four animated segments with decreasing size.
    segments = [(3.0,(34,211,238)),(4.0,(56,189,248)),(5.4,(125,211,252)),(7.0,(224,242,254))]
    glow = Image.new("RGBA",(W,H),(0,0,0,0))
    gdraw = ImageDraw.Draw(glow)
    positions=[]
    for idx, (radius,color) in enumerate(segments):
        distance=head_dist-(3-idx)*1.3
        if distance < 0:
            continue
        x,y=point_at(distance)
        positions.append((x,y,radius,color))
        gdraw.ellipse((x-radius-3,y-radius-3,x+radius+3,y+radius+3), fill=(*color,140))
    glow=glow.filter(ImageFilter.GaussianBlur(6))
    frame=Image.alpha_composite(frame,glow)
    d=ImageDraw.Draw(frame)
    for x,y,radius,color in positions:
        d.ellipse((x-radius,y-radius,x+radius,y+radius), fill=color, outline=(56,189,248), width=1)
    return frame.convert("RGB")

def main():
    out = Path("assets/profile/personal-snake.gif")
    out.parent.mkdir(parents=True, exist_ok=True)
    rgb_frames=[]
    for word in WORDS:
        data=build_word(word)
        for frame_no in range(FRAMES_PER_WORD):
            progress=frame_no/(FRAMES_PER_WORD-1)
            rgb_frames.append(draw_frame(data, progress))

    # Use one shared palette for every frame to prevent color flicker and ghosting.
    sample = Image.new("RGB", (W, H * min(12, len(rgb_frames))), BG)
    for i in range(min(12, len(rgb_frames))):
        sample.paste(rgb_frames[i], (0, i * H))
    palette_source = sample.resize((256, 1)).quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    frames = [frame.quantize(palette=palette_source, dither=Image.Dither.NONE) for frame in rgb_frames]
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0, optimize=False, disposal=2)
    print(f"Generated {out} with {len(frames)} frames at {1000/FRAME_MS:.0f} fps.")

if __name__ == "__main__":
    main()
