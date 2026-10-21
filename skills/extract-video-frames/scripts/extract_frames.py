#!/usr/bin/env python3
"""Extract still frames from a video file with ffmpeg.

Modes (pick one):
  --every SECONDS      one frame every N seconds
  --count N            N frames spread evenly over the video
  --at T1,T2,...       frames at given times (seconds or mm:ss or hh:mm:ss)
  --scenes             one frame per scene change (threshold: --sensitivity)

Output:
  --format jpg|png|webp     image format (default jpg)
  --pack zip|pdf|none       also bundle frames into a ZIP or a one-picture-per-page PDF
  --start / --end           limit to a part of the video
  --width                   scale frames to this width (default: original size)

Prints a JSON summary on stdout.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile

MAX_FRAMES = 300


def find_ffmpeg():
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ff and fp:
        return ff, fp
    try:
        import imageio_ffmpeg  # type: ignore
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "--break-system-packages", "imageio-ffmpeg"],
                       check=False, capture_output=True)
        try:
            import imageio_ffmpeg  # type: ignore
        except ImportError:
            fail("ffmpeg is not available and could not be installed.")
    return imageio_ffmpeg.get_ffmpeg_exe(), None


def fail(msg):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    sys.exit(1)


def parse_time(s):
    s = s.strip()
    parts = s.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        fail(f"Cannot read the time '{s}'. Use seconds (75), mm:ss (1:15) or hh:mm:ss.")
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def fmt_time(t):
    ms = int(round((t - int(t)) * 1000))
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h:02d}-{m:02d}-{s:02d}.{ms:03d}"


def probe_duration(ffmpeg, ffprobe, path):
    if ffprobe:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            d = line.split("Duration:")[1].split(",")[0].strip()
            if d != "N/A":
                return parse_time(d)
    return None


def grab(ffmpeg, path, t, out, width, fmt):
    vf = [f"scale={width}:-2"] if width else []
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += quality_args(fmt) + [out]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(out) and os.path.getsize(out) > 0


def quality_args(fmt):
    if fmt == "jpg":
        return ["-q:v", "2"]
    if fmt == "webp":
        return ["-quality", "90"]
    return []


MIN_SCENE_S = 0.3       # shorter scenes are glued to the previous one (blank fade frames are dropped later)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def ensure_libs():
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages",
                        "numpy", "Pillow"], capture_output=True)


def scene_middles(cuts, start, end):
    """One time per scene: the middle of each scene, so cuts and fades are avoided."""
    bounds = [start] + [c for c in cuts if start + 0.01 < c < end] + [end]
    segs = []
    for a, b in zip(bounds, bounds[1:]):
        if segs and b - a < MIN_SCENE_S:
            segs[-1][1] = b
        else:
            segs.append([a, b])
    if len(segs) > 1 and segs[0][1] - segs[0][0] < MIN_SCENE_S:
        segs[1][0] = segs[0][0]
        segs.pop(0)
    return [(a + b) / 2 for a, b in segs]


def drop_repeats(files, base, out, fmt, sensitivity):
    """Remove a frame that looks the same as the one before it (same slide after a fade,
    same screen), then renumber the remaining files."""
    import scenecut
    kept, last, merged = [], None, 0
    for f in files:
        t = scenecut.signature_from_image(f["file"])
        if (scenecut.is_flat(t) and len(files) > 1) or (
                last is not None and scenecut.is_same(t, last, sensitivity)):
            os.remove(f["file"])
            merged += 1
            continue
        kept.append(f)
        last = t
    for i, f in enumerate(kept, 1):
        name = f"{base}_{i:03d}_{fmt_time(f['time'])}.{fmt}"
        p = os.path.join(out, name)
        if p != f["file"]:
            os.replace(f["file"], p)
            f["file"] = p
    return kept, merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="frames")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--every", type=float)
    g.add_argument("--count", type=int)
    g.add_argument("--at")
    g.add_argument("--scenes", action="store_true")
    ap.add_argument("--sensitivity", choices=["low", "normal", "high"], default="normal")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--format", choices=["jpg", "png", "webp"], default="jpg")
    ap.add_argument("--width", type=int)
    ap.add_argument("--pack", choices=["zip", "pdf", "none"], default="zip")
    a = ap.parse_args()

    if not os.path.isfile(a.video):
        fail(f"File not found: {a.video}")
    ffmpeg, ffprobe = find_ffmpeg()
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", a.video], capture_output=True, text=True)
    if " Video:" not in r.stderr or "attached pic" in r.stderr.split(" Video:")[1].split("\n")[0]:
        fail("This file has no video picture (it may be audio only). Attach a video file.")
    dur = probe_duration(ffmpeg, ffprobe, a.video)
    if not dur:
        fail("Could not read this video. It may be damaged or not a video file.")

    start = parse_time(a.start) if a.start else 0.0
    end = min(parse_time(a.end), dur) if a.end else dur
    if end <= start:
        fail("The end of the part must be after its start.")

    if a.every:
        if a.every <= 0:
            fail("--every must be greater than 0.")
        times, t = [], start
        while t < end and len(times) <= MAX_FRAMES:
            times.append(t)
            t += a.every
    elif a.count:
        n = max(1, a.count)
        span = end - start
        times = [start + span * (i + 0.5) / n for i in range(n)]
    elif a.at:
        times = [parse_time(x) for x in a.at.split(",") if x.strip()]
        bad = [t for t in times if t < 0 or t > dur]
        if bad:
            fail(f"Some times are outside the video (length {dur:.1f} s): {bad}")
    else:
        ensure_libs()
        import scenecut
        cuts = scenecut.detect_cuts(ffmpeg, a.video, start if a.start else None,
                                    end if a.end else None, a.sensitivity, dur)
        times = scene_middles(cuts, start, end)

    truncated = len(times) > MAX_FRAMES
    times = times[:MAX_FRAMES]

    os.makedirs(a.out, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.video))[0]
    files = []
    for i, t in enumerate(times, 1):
        t = min(max(t, 0), max(dur - 0.05, 0))
        name = f"{base}_{i:03d}_{fmt_time(t)}.{a.format}"
        p = os.path.join(a.out, name)
        if grab(ffmpeg, a.video, t, p, a.width, a.format):
            files.append({"file": p, "time": round(t, 3)})

    if not files:
        fail("No frames could be read. The video codec may be unsupported; try MP4 (H.264).")

    merged_same = 0
    if a.scenes:
        files, merged_same = drop_repeats(files, base, a.out, a.format, a.sensitivity)

    bundle = None
    if a.pack == "zip":
        bundle = os.path.join(a.out, f"{base}_frames.zip")
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_STORED) as z:
            for f in files:
                z.write(f["file"], os.path.basename(f["file"]))
    elif a.pack == "pdf":
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                            "--break-system-packages", "Pillow"], capture_output=True)
            from PIL import Image  # type: ignore
        imgs = [Image.open(f["file"]).convert("RGB") for f in files]
        bundle = os.path.join(a.out, f"{base}_frames.pdf")
        imgs[0].save(bundle, save_all=True, append_images=imgs[1:], resolution=150)

    print(json.dumps({
        "ok": True,
        "video_duration_s": round(dur, 2),
        "frames": len(files),
        "truncated_to_max": truncated,
        "repeated_scenes_merged": merged_same,
        "files": files,
        "bundle": bundle,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
