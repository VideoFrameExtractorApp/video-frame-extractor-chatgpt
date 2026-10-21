---
name: extract-video-frames
description: Extract still frames from a video file the user attached (MP4, WebM, MOV, MKV) and return them as JPG, PNG or WebP images, a ZIP, or a one-picture-per-page PDF. Use when the user asks to get frames, stills, screenshots or thumbnails from a video as files, a frame at a specific time, a picture every N seconds, N pictures spread over the video, or one picture per scene or slide change. To answer questions about what the video shows, use understand-video instead.
---

# Extract video frames

Turn an attached video into still pictures with `scripts/extract_frames.py` (ffmpeg under the hood). Do the task directly and quickly; do not ask questions when a sensible default exists.

## 1. Pick the mode from the request

| User says | Flag |
|---|---|
| "frame at 1:23", "a still at 10s and 45s" | `--at 1:23` / `--at 10,45` |
| "a frame every 5 seconds" | `--every 5` |
| "20 frames", "a few stills from the whole video" | `--count 20` (a few → 8) |
| "every scene", "each slide", "key frames", no mode given | `--scenes` |

Scene sensitivity: "fewer pictures" → `--sensitivity low`, "more" → `high`. Lecture/screen recordings with small changes → `high`.

Optional: `--start 0:30 --end 2:00` for part of the video, `--format png|webp` (default jpg), `--width 1280` to shrink, `--pack pdf` when the user wants a PDF, `--pack none` for a single frame. Default `--pack zip`. Maximum 300 frames per run.

## 2. Run

```bash
python3 <skill_dir>/scripts/extract_frames.py "<video path>" --out <output dir> <mode flags>
```

The script prints JSON: `ok`, `frames`, `files` (path + time in seconds), `bundle` (ZIP/PDF path), or `error`.

## 3. Deliver

- Give the user the bundle (ZIP or PDF). For 1–4 frames, give the images themselves. Show one or two frames inline when the interface allows.
- One short line: how many frames, from which part, which format. File names contain the timestamp (`name_003_00-01-23.500.jpg`).
- On `error`, explain it in plain words and suggest the fix the message gives (for example, convert to MP4 H.264).
