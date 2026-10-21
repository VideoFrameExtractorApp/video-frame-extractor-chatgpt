#!/usr/bin/env python3
"""Turn a video into a compact package an AI assistant can read: key frames + contact sheet + index.

Steps:
  1. find scene changes: whole-frame cuts and, for screen recordings, new screen states
     (a window, panel or notification appears and stays) - see scenecut.py
  2. drop very short scenes, split very long ones so nothing is missed
  3. take one frame from the middle of each scene (avoids transitions and fades)
  4. merge neighbouring scenes that look the same (same slide, same shot)
  5. keep at most --max-frames, merging the most similar neighbours first
  6. write frames (long side --size px), contact_sheet.jpg, index.md and a ZIP

Prints a JSON summary on stdout.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile

MIN_SCENE_S = 0.3       # scenes shorter than this are merged into the previous one
                        # (fast edits like TikTok cut every ~0.5 s; blank fade frames are dropped later)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def fail(msg):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    sys.exit(1)


def ensure_libs():
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages",
                        "numpy", "Pillow"], capture_output=True)


def find_ffmpeg():
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ff:
        return ff, fp
    try:
        import imageio_ffmpeg  # type: ignore
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages",
                        "imageio-ffmpeg"], capture_output=True)
        try:
            import imageio_ffmpeg  # type: ignore
        except ImportError:
            fail("ffmpeg is not available and could not be installed.")
    return imageio_ffmpeg.get_ffmpeg_exe(), None


def parse_time(s):
    total = 0.0
    try:
        for p in str(s).strip().split(":"):
            total = total * 60 + float(p)
    except ValueError:
        fail(f"Cannot read the time '{s}'. Use seconds (75), mm:ss (1:15) or hh:mm:ss.")
    return total


def tc(t, sep=":"):
    t = int(round(t))
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}{sep}{m:02d}{sep}{s:02d}" if h else f"{m}{sep}{s:02d}"


def probe(ffmpeg, ffprobe, path):
    dur, w, h = None, None, None
    if ffprobe:
        r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height:format=duration",
                            "-of", "json", path], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            dur = float(d["format"]["duration"])
            w, h = d["streams"][0]["width"], d["streams"][0]["height"]
        except (ValueError, KeyError, IndexError, TypeError):
            pass
    if dur is None:
        r = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
        for line in r.stderr.splitlines():
            if "Duration:" in line:
                v = line.split("Duration:")[1].split(",")[0].strip()
                if v != "N/A":
                    dur = parse_time(v)
            if " Video:" in line and w is None:
                for tok in line.replace(",", " ").split():
                    if "x" in tok and tok.split("x")[0].isdigit() and tok.split("x")[1].isdigit():
                        w, h = int(tok.split("x")[0]), int(tok.split("x")[1])
                        break
    return dur, w, h


def build_segments(cuts, start, end, max_scene):
    bounds = [start] + [c for c in cuts if start < c < end] + [end]
    segs = []
    for a, b in zip(bounds, bounds[1:]):
        if segs and b - a < MIN_SCENE_S:
            segs[-1][1] = b          # too short: glue to previous scene
        else:
            segs.append([a, b])
    if len(segs) > 1 and segs[0][1] - segs[0][0] < MIN_SCENE_S:
        segs[1][0] = segs[0][0]
        segs.pop(0)
    out = []
    for a, b in segs:                # long scene: split so nothing is missed
        n = max(1, int((b - a) // max_scene) + (1 if (b - a) % max_scene > max_scene / 2 else 0))
        step = (b - a) / n
        for i in range(n):
            out.append({"start": a + i * step, "end": a + (i + 1) * step, "split": n > 1})
    return out


def grab(ffmpeg, path, t, out, scale):
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
           "-vf", scale, "-q:v", "3", out]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(out) and os.path.getsize(out) > 0


def merge(scenes, i):
    """Merge scene i+1 into scene i (keep the frame of the longer one)."""
    a, b = scenes[i], scenes[i + 1]
    keep = a if (a["end"] - a["start"]) >= (b["end"] - b["start"]) else b
    drop = b if keep is a else a
    if os.path.exists(drop["file"]):
        os.remove(drop["file"])
    keep = dict(keep, start=a["start"], end=b["end"])
    scenes[i:i + 2] = [keep]


def tc_ms(t):
    """Time with hundredths of a second, e.g. 0:05.50 (for dense mode)."""
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def contact_sheet(scenes, out, labels=None):
    from PIL import Image, ImageDraw, ImageFont
    with Image.open(scenes[0]["file"]) as im:
        ratio = im.height / im.width
    cols, tile_w = (8, 180) if ratio > 1 else (5, 300)   # portrait videos: narrower tiles
    cols = min(cols, len(scenes))
    tile_h = int(tile_w * ratio)
    label_h = 22
    rows = (len(scenes) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w, rows * (tile_h + label_h)), "white")
    font = None
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 15)
            break
    if font is None:
        try:
            font = ImageFont.load_default(size=15)
        except TypeError:
            font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for i, s in enumerate(scenes):
        x, y = (i % cols) * tile_w, (i // cols) * (tile_h + label_h)
        with Image.open(s["file"]) as im:
            sheet.paste(im.convert("RGB").resize((tile_w, tile_h)), (x, y + label_h))
        label = labels[i] if labels else f"#{i + 1}  {tc(s['start'])}"
        d.text((x + 4, y + 3), label, fill="black", font=font)
    # Chat models resize images whose long side exceeds ~1568 px; keep the sheet under that
    if max(sheet.size) > 1568:
        k = 1568 / max(sheet.size)
        sheet = sheet.resize((int(sheet.width * k), int(sheet.height * k)))
    sheet.save(out, quality=85)
    return sheet.size


def tokens(w, h):
    return int(w * h / 750)


BLUR_STEP = 0.2         # seconds between the neighbours that are compared
BLUR_SWAP = 0.7         # swap only if the middle frame scores below 70% of the sharpest neighbour


def sharpness(rgb):
    """Variance of the 3x3 Laplacian on a 320 px gray copy (same method as the VFE sharpness module).
    Only used to compare neighbouring frames of one scene, never as an absolute verdict."""
    import numpy as np
    g = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def avoid_blur(ffmpeg, path, scene, t):
    """Return t, or a neighbour within +-0.4 s (inside the scene) if t is clearly blurred."""
    import numpy as np
    lo = scene["start"] + 0.1 * (scene["end"] - scene["start"])
    hi = scene["end"] - 0.1 * (scene["end"] - scene["start"])
    if hi - lo < 4 * BLUR_STEP:
        return t
    first = max(lo, t - 2 * BLUR_STEP)
    W, H = 320, 240
    cmd = [ffmpeg, "-v", "error", "-ss", f"{first:.3f}", "-i", path, "-an",
           "-vf", f"fps={1 / BLUR_STEP},scale={W}:{H}:flags=neighbor", "-frames:v", "5",
           "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True)
    n = len(r.stdout) // (W * H * 3)
    if n < 2:
        return t
    frames = np.frombuffer(r.stdout[:n * W * H * 3], np.uint8).reshape(n, H, W, 3).astype(np.float64)
    cand = [(first + k * BLUR_STEP, sharpness(frames[k])) for k in range(n)
            if first + k * BLUR_STEP <= hi]
    if not cand:
        return t
    mid = min(cand, key=lambda c: abs(c[0] - t))
    best = max(cand, key=lambda c: c[1])
    return best[0] if mid[1] < BLUR_SWAP * best[1] else t


MAX_DENSE = 240         # most frames dense mode will take (about 10 sheet pages)


def dense_package(a, ffmpeg, dur, w, h, start, end, scale):
    """Dense mode: a frame every --every seconds, all kept in order (no scene logic),
    contact sheets split into pages, times with hundredths of a second.
    For reading on-screen text / subtitles line by line, and for motion analysis."""
    from PIL import Image
    span = end - start
    n = int(span / a.every + 1e-9) + 1
    if n > MAX_DENSE:
        fail(f"That would be {n} frames; dense mode takes at most {MAX_DENSE}. "
             f"Use a shorter part (--start/--end) or a larger --every "
             f"(at least {span / (MAX_DENSE - 1):.2f} s for this part).")
    fdir = os.path.join(a.out, "frames")
    os.makedirs(fdir, exist_ok=True)
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", a.video,
           "-an", "-vf", f"fps={1 / a.every},{scale}", "-q:v", "3", "-frames:v", str(n),
           os.path.join(fdir, "tmp_%04d.jpg")]
    subprocess.run(cmd, capture_output=True)
    raw = sorted(f for f in os.listdir(fdir) if f.startswith("tmp_"))
    if not raw:
        fail("No frames could be read. The video codec may be unsupported; try MP4 (H.264).")
    items = []
    for k, f in enumerate(raw):
        t = start + k * a.every
        dst = os.path.join(fdir, f"{k + 1:03d}_{tc_ms(t).replace(':', '-')}.jpg")
        os.replace(os.path.join(fdir, f), dst)
        items.append({"start": t, "end": min(t + a.every, end), "t": t, "file": dst})
    with Image.open(items[0]["file"]) as im:
        portrait = im.height > im.width
        fw, fh_ = im.size
    per_page = 24 if portrait else 25
    sheets, sheet_tokens = [], 0
    for p in range(0, len(items), per_page):
        chunk = items[p:p + per_page]
        out = os.path.join(a.out, f"contact_sheet_{p // per_page + 1:02d}.jpg")
        labels = [f"#{p + i + 1} {tc_ms(it['t'])}" for i, it in enumerate(chunk)]
        sw, sh = contact_sheet(chunk, out, labels)
        sheets.append(out)
        sheet_tokens += tokens(sw, sh)
    total_tokens = tokens(fw, fh_) * len(items)

    idx = os.path.join(a.out, "index.md")
    with open(idx, "w", encoding="utf-8") as fh:
        fh.write(f"# Video package (dense): {os.path.basename(a.video)}\n\n")
        fh.write(f"- Length: {tc(dur)}; analysed {tc_ms(start)}–{tc_ms(end)}, "
                 f"one frame every {a.every:g} s\n")
        if w and h:
            fh.write(f"- Original size: {w}×{h}\n")
        fh.write(f"- Frames: {len(items)}, in time order, nothing merged\n")
        fh.write(f"- Contact sheets: {len(sheets)} pages ≈ {sheet_tokens} tokens in total; "
                 f"all frames ≈ {total_tokens} tokens\n")
        fh.write("- Pictures only: speech and sound are not included.\n\n")
        fh.write("Read the contact sheets in order (`contact_sheet_01.jpg`, `_02`, ...). "
                 "Each label is `#number time` with hundredths of a second. "
                 "Open single frames only where you need detail.\n\n")
        fh.write("| # | Time | Frame |\n|---|---|---|\n")
        for k, it in enumerate(items, 1):
            fh.write(f"| {k} | {tc_ms(it['t'])} | frames/{os.path.basename(it['file'])} |\n")

    base = os.path.splitext(os.path.basename(a.video))[0]
    zpath = os.path.join(a.out, f"{base}_package.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        z.write(idx, "index.md")
        for s in sheets:
            z.write(s, os.path.basename(s))
        for it in items:
            z.write(it["file"], "frames/" + os.path.basename(it["file"]))

    print(json.dumps({
        "ok": True,
        "mode": "dense",
        "video_duration_s": round(dur, 2),
        "every_s": a.every,
        "frames": len(items),
        "index": idx,
        "contact_sheets": sheets,
        "zip": zpath,
        "est_tokens": {"contact_sheets": sheet_tokens, "all_frames": total_tokens},
    }, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="video_package")
    ap.add_argument("--max-frames", type=int, default=40)
    ap.add_argument("--size", type=int, default=1024, help="long side of each frame, px")
    ap.add_argument("--sensitivity", choices=["low", "normal", "high"], default="normal")
    ap.add_argument("--max-scene", type=float, default=None,
                    help="split scenes longer than this many seconds (default: adaptive)")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--every", type=float, default=None,
                    help="dense mode: one frame every N seconds, e.g. 0.5 for subtitles, "
                         "0.033 for every frame of a 30 fps clip")
    a = ap.parse_args()
    if a.every is not None and not (1 / 120 <= a.every <= 60):
        fail("--every must be between 0.0083 and 60 seconds.")

    if not os.path.isfile(a.video):
        fail(f"File not found: {a.video}")
    ensure_libs()
    ffmpeg, ffprobe = find_ffmpeg()
    import scenecut
    if not scenecut.has_video(ffmpeg, a.video):
        fail("This file has no video picture (it may be audio only). Attach a video file.")
    dur, w, h = probe(ffmpeg, ffprobe, a.video)
    if not dur:
        fail("Could not read this video. It may be damaged or not a video file.")

    start = parse_time(a.start) if a.start else 0.0
    end = min(parse_time(a.end), dur) if a.end else dur
    if end <= start:
        fail("The end of the part must be after its start.")
    span = end - start
    if a.every is not None:
        dense_scale = (f"scale='if(gte(iw,ih),min({a.size},iw),-2)':"
                       f"'if(gte(iw,ih),-2,min({a.size},ih))'")
        dense_package(a, ffmpeg, dur, w, h, start, end, dense_scale)
        return
    max_frames = max(4, min(a.max_frames, 120))
    max_scene = a.max_scene or max(20.0, min(120.0, span / max_frames * 1.5))

    import scenecut
    cuts = scenecut.detect_cuts(ffmpeg, a.video, start, end, a.sensitivity, dur)
    scenes = build_segments(cuts, start, end, max_scene)
    # safety cap on how many frames we decode: glue the shortest scene to a neighbour
    # (never cut the end of the video off)
    cap = max_frames * 4
    while len(scenes) > cap:
        k = min(range(len(scenes)), key=lambda j: scenes[j]["end"] - scenes[j]["start"])
        if k == len(scenes) - 1 or (k > 0 and scenes[k - 1]["end"] - scenes[k - 1]["start"]
                                    < scenes[k + 1]["end"] - scenes[k + 1]["start"]):
            scenes[k - 1]["end"] = scenes[k]["end"]
        else:
            scenes[k + 1]["start"] = scenes[k]["start"]
        scenes.pop(k)

    # limit the long side after ffmpeg applies phone rotation (portrait video is stored as landscape)
    scale = (f"scale='if(gte(iw,ih),min({a.size},iw),-2)':"
             f"'if(gte(iw,ih),-2,min({a.size},ih))'")

    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    times = [min((s["start"] + s["end"]) / 2, max(dur - 0.05, 0)) for s in scenes]

    kept = []
    for i, s in enumerate(scenes):
        t = times[i]
        f = os.path.join(a.out, "frames", f"tmp_{i:04d}.jpg")
        if grab(ffmpeg, a.video, t, f, scale):
            kept.append(dict(s, t=t, file=f, thumb=scenecut.signature_from_image(f)))
    if not kept:
        fail("No frames could be read. The video codec may be unsupported; try MP4 (H.264).")

    # 3b. drop blank frames (black/white flash in a fade) by gluing them to a neighbour
    i = 0
    while len(kept) > 1 and i < len(kept):
        if scenecut.is_flat(kept[i]["thumb"]):
            blank = kept.pop(i)
            if os.path.exists(blank["file"]):
                os.remove(blank["file"])
            if i > 0:
                kept[i - 1] = dict(kept[i - 1], end=blank["end"])   # previous scene absorbs the blank
            else:
                kept[0] = dict(kept[0], start=blank["start"])
            continue
        i += 1
    # 3c. drop short blurred in-between scenes (focus pull, whip pan): a scene under 1.5 s whose
    #     frame is far blurrier than both neighbours is a transition, not content
    def frame_sharpness(path):
        import numpy as np
        from PIL import Image
        with Image.open(path) as im:
            w = 320
            h = max(3, int(im.height * w / im.width))
            rgb = np.asarray(im.convert("RGB").resize((w, h), Image.NEAREST), dtype=np.float64)
        return sharpness(rgb)
    for s in kept:
        s["sharp"] = frame_sharpness(s["file"])
    def coarse(sig):
        # 30x17 block averages: the overall picture without fine detail
        return sig.reshape(17, 8, 30, 8).mean(axis=(1, 3))

    def looks_like(a, b):
        import numpy as np
        return float(np.mean(np.abs(coarse(a["thumb"]) - coarse(b["thumb"])))) < 0.08

    i = 1
    while 0 < i < len(kept) - 1:
        s = kept[i]
        # blurred, not just plain: the same picture as a neighbour, only without detail
        if (s["end"] - s["start"] < 1.5
                and s["sharp"] < 0.35 * min(kept[i - 1]["sharp"], kept[i + 1]["sharp"])
                and (looks_like(s, kept[i - 1]) or looks_like(s, kept[i + 1]))):
            blur = kept.pop(i)
            if os.path.exists(blur["file"]):
                os.remove(blur["file"])
            kept[i - 1] = dict(kept[i - 1], end=blur["end"])
            continue
        i += 1
    # 4. merge neighbours that look the same
    i, merged_same = 0, 0
    while i < len(kept) - 1:
        if scenecut.is_same(kept[i]["thumb"], kept[i + 1]["thumb"], a.sensitivity):
            merge(kept, i)
            merged_same += 1
        else:
            i += 1
    # 5. respect the frame budget: merge the most similar neighbours first,
    #    but prefer short merges so the whole timeline stays evenly covered
    over_budget = 0

    def merge_cost(k):
        length = (kept[k + 1]["end"] - kept[k]["start"]) / span
        return scenecut.changed_area(kept[k]["thumb"], kept[k + 1]["thumb"]) + 0.5 * length

    while len(kept) > max_frames:
        j = min(range(len(kept) - 1), key=merge_cost)
        merge(kept, j)
        over_budget += 1

    # safety net against an obviously blurred frame, only for the frames we keep:
    # check 5 neighbours (+-0.4 s) inside the scene and swap only if the frame is clearly worse
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        better = list(pool.map(lambda s: avoid_blur(ffmpeg, a.video, s, s["t"]), kept))
    swaps = 0
    for s, t in zip(kept, better):
        if abs(t - s["t"]) > 0.01 and grab(ffmpeg, a.video, t, s["file"], scale):
            s["t"] = t
            swaps += 1

    base = os.path.splitext(os.path.basename(a.video))[0]
    total_tokens = 0
    from PIL import Image
    for n, s in enumerate(kept, 1):
        name = f"{n:03d}_{tc(s['t'], '-')}.jpg"
        dst = os.path.join(a.out, "frames", name)
        os.replace(s["file"], dst)
        s["file"] = dst
        with Image.open(dst) as im:
            s["w"], s["h"] = im.size
        total_tokens += tokens(s["w"], s["h"])
    for f in os.listdir(os.path.join(a.out, "frames")):
        if f.startswith("tmp_"):
            os.remove(os.path.join(a.out, "frames", f))

    sheet = os.path.join(a.out, "contact_sheet.jpg")
    sw, sh = contact_sheet(kept, sheet)
    sheet_tokens = tokens(sw, sh)

    idx = os.path.join(a.out, "index.md")
    with open(idx, "w", encoding="utf-8") as fh:
        fh.write(f"# Video package: {os.path.basename(a.video)}\n\n")
        fh.write(f"- Length: {tc(dur)}" + (f" (analysed {tc(start)}–{tc(end)})" if a.start or a.end else "") + "\n")
        if w and h:
            fh.write(f"- Original size: {w}×{h}\n")
        fh.write(f"- Key frames: {len(kept)} (one per scene; repeated scenes merged)\n")
        fh.write(f"- Estimated cost to view: contact sheet ≈ {sheet_tokens} tokens, "
                 f"all frames ≈ {total_tokens} tokens\n")
        fh.write("- Pictures only: speech and sound are not included.\n\n")
        fh.write("Start with `contact_sheet.jpg` (all frames with times), "
                 "then open only the frames you need.\n\n")
        fh.write("| # | From | To | Frame |\n|---|---|---|---|\n")
        for n, s in enumerate(kept, 1):
            note = " (long scene, part)" if s.get("split") else ""
            fh.write(f"| {n} | {tc(s['start'])} | {tc(s['end'])} | frames/{os.path.basename(s['file'])}{note} |\n")

    zpath = os.path.join(a.out, f"{base}_package.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        z.write(idx, "index.md")
        z.write(sheet, "contact_sheet.jpg")
        for s in kept:
            z.write(s["file"], "frames/" + os.path.basename(s["file"]))

    print(json.dumps({
        "ok": True,
        "video_duration_s": round(dur, 2),
        "scenes_found": len(scenes),
        "merged_same": merged_same,
        "merged_for_budget": over_budget,
        "blurred_frames_replaced": swaps,
        "frames": len(kept),
        "index": idx,
        "contact_sheet": sheet,
        "zip": zpath,
        "est_tokens": {"contact_sheet": sheet_tokens, "all_frames": total_tokens},
        "scenes": [{"n": n, "from": round(s["start"], 2), "to": round(s["end"], 2),
                    "file": s["file"]} for n, s in enumerate(kept, 1)],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
