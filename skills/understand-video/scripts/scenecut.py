"""Scene detection shared by both skills (keep the two copies identical).

Three detectors, results merged:
  * whole-frame cuts (ffmpeg scene score): slides, film cuts
  * screen states: part of the screen changes and then stays still
    (a window opens, a panel or notification appears, a new page loads).
    Built for screen recordings, where the background barely changes.
  * view drift: a moving camera has gradually turned or walked to a different view
    (phone and action-camera video, where nothing is ever still and there are no cuts).
  * overlays: graphics, diagrams or text change while part of the frame never stops moving
    (a talking head, a person at a desk). Areas that move almost all the time are ignored;
    a new state is noted when the rest of the frame changes and settles.
"""
import subprocess
from collections import deque
import tempfile

import numpy as np

SIG_W, SIG_H = 240, 136   # size used to compare frames
PIX = 0.06                # a pixel counts as changed if its brightness differs by more than 6%
STILL = 0.002             # the screen is "still" if < 0.2% of pixels moved since the previous sample

FFMPEG_THR = {"low": 0.4, "normal": 0.27, "high": 0.15}
AREA_THR = {"low": 0.015, "normal": 0.006, "high": 0.003}   # share of the screen that must change
DRIFT_THR = {"low": 0.16, "normal": 0.12, "high": 0.09}     # mean change of a blurred view
DRIFT_MIN_GAP = 2.0       # seconds between two view-drift cuts
OVERLAY_THR = {"low": 0.03, "normal": 0.015, "high": 0.008}  # share of the calm area that must change
OVERLAY_STILL = 0.004     # the calm area is "still" if < 0.4% of it moved since the previous sample
OVERLAY_SETTLE = 0.3      # ...or if what moves is under 30% of how much it changed overall
OVERLAY_MIN_GAP = 1.5     # seconds between two overlay cuts
BUSY_WINDOW = 20          # samples (10 s at 2 fps) used to learn which areas move all the time
BUSY_SHARE = 0.5          # a block is "always moving" if it changed in at least half of them
MIN_CALM = 0.3            # the overlay detector stays silent if less than 30% of the frame is calm


def changed_area(a, b):
    return float(np.mean(np.abs(a - b) > PIX))


def signature_from_image(path):
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("L").resize((SIG_W, SIG_H)), dtype=np.float32) / 255.0


def _range_args(start, end):
    args = []
    if start:
        args += ["-ss", f"{start:.3f}"]
    if end:
        args += ["-to", f"{end:.3f}"]
    return args


def start_whole_frame_cuts(ffmpeg, path, start, end, sensitivity):
    """Start the ffmpeg scene detector in the background; read it with finish_whole_frame_cuts."""
    thr = FFMPEG_THR[sensitivity]
    cmd = [ffmpeg, "-v", "info", "-hide_banner", "-nostats"] + _range_args(start, end) + [
        "-i", path, "-an", "-vf", f"scale=320:-2,select='gt(scene,{thr})',showinfo",
        "-vsync", "vfr", "-f", "null", "-"]
    # log goes to a temp file, not a pipe: a full pipe would stall ffmpeg while we read the other detector
    log = tempfile.TemporaryFile(mode="w+")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=log, text=True)
    return proc, log


def finish_whole_frame_cuts(job, start):
    proc, log = job
    proc.wait()
    log.seek(0)
    err = log.read()
    log.close()
    cuts = []
    for line in err.splitlines():
        if "showinfo" in line and "pts_time:" in line:
            try:
                cuts.append((start or 0) + float(line.split("pts_time:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    return cuts


def _blur(f):
    """240x136 -> 30x17 block average: ignores small motion, keeps the overall view."""
    return f.reshape(SIG_H // 8, 8, SIG_W // 8, 8).mean(axis=(1, 3))


def screen_and_drift_cuts(ffmpeg, path, start, end, sensitivity, duration):
    area_thr = AREA_THR[sensitivity]
    drift_thr = DRIFT_THR[sensitivity]
    span = (end or duration) - (start or 0)
    fps = 2.0 if span <= 1800 else max(0.5, 3600.0 / span)
    cmd = [ffmpeg, "-v", "error"] + _range_args(start, end) + [
        "-i", path, "-an", "-vf", f"fps={fps},scale={SIG_W}:{SIG_H},format=gray",
        "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = SIG_W * SIG_H
    prev = ref = drift_ref = ov_ref = None
    pending = ov_pending = None
    last_cut = last_ov = -1e9
    busy_hist = deque(maxlen=BUSY_WINDOW)
    ov_thr = OVERLAY_THR[sensitivity]
    cuts = []
    i = 0
    try:
        while True:
            b = p.stdout.read(size)
            if len(b) < size:
                break
            f = np.frombuffer(b, np.uint8).astype(np.float32) / 255.0
            t = (start or 0) + i / fps
            if ref is None:
                ref = ov_ref = f
                drift_ref = _blur(f)
            else:
                vs_ref = changed_area(f, ref)
                if vs_ref > area_thr:
                    if pending is None:
                        pending = t          # the screen started to change here
                    if changed_area(f, prev) < STILL:
                        cuts.append(pending)  # ...and has now settled in a new state
                        last_cut = pending
                        ref = ov_ref = f
                        drift_ref = _blur(f)
                        pending = None
                else:
                    pending = None           # it went back to how it was (e.g. a hover)
                blurred = _blur(f)
                if (float(np.mean(np.abs(blurred - drift_ref))) > drift_thr
                        and t - last_cut >= DRIFT_MIN_GAP):
                    cuts.append(t)           # the camera now shows a different view
                    last_cut = t
                    drift_ref = blurred
                    ref = ov_ref = f
                    pending = None
                # overlays over an always-moving area (talking head + graphics)
                moved = np.abs(f - prev) > PIX
                busy_hist.append(moved.reshape(SIG_H // 8, 8, SIG_W // 8, 8).mean(axis=(1, 3)) > 0.1)
                if len(busy_hist) >= 6:
                    busy = np.mean(busy_hist, axis=0) >= BUSY_SHARE
                    calm = ~np.repeat(np.repeat(busy, 8, axis=0), 8, axis=1).reshape(-1)
                    if calm.mean() >= MIN_CALM and busy.any():
                        vs_ov = float(np.mean((np.abs(f - ov_ref) > PIX)[calm]))
                        if vs_ov > ov_thr:
                            if ov_pending is None:
                                ov_pending = t
                            # settled: what still moves is small next to how much changed
                            # (subtitles keep flickering while a new diagram stays)
                            settle = max(OVERLAY_STILL, OVERLAY_SETTLE * vs_ov)
                            if (float(np.mean(moved[calm])) < settle
                                    and t - last_ov >= OVERLAY_MIN_GAP):
                                at = max(ov_pending, last_ov + 0.5)
                                cuts.append(at)           # graphics changed and settled
                                last_ov = at
                                ov_ref = f
                                ov_pending = None
                        else:
                            ov_pending = None
            prev = f
            i += 1
    finally:
        p.stdout.close()
        p.wait()
    return cuts


def detect_cuts(ffmpeg, path, start, end, sensitivity, duration):
    """Sorted cut times (seconds) from all detectors, near-duplicates (< 0.5 s) removed."""
    job = start_whole_frame_cuts(ffmpeg, path, start, end, sensitivity)   # runs in parallel
    other = screen_and_drift_cuts(ffmpeg, path, start, end, sensitivity, duration)
    cuts = sorted(finish_whole_frame_cuts(job, start) + other)
    out = []
    for c in cuts:
        if not out or c - out[-1] >= 0.5:
            out.append(c)
    return out


def is_flat(sig):
    """A blank frame: black or white screen in a fade or flash, nothing to look at."""
    return float(np.std(sig)) < 0.03


def has_video(ffmpeg, path):
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True)
    return " Video:" in r.stderr and "attached pic" not in r.stderr.split(" Video:")[1].split("\n")[0]


def is_same(sig_a, sig_b, sensitivity):
    """Two frames show the same thing (same slide after a fade, same screen)."""
    return changed_area(sig_a, sig_b) < AREA_THR[sensitivity]
