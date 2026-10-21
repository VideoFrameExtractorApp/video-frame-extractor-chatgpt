---
name: understand-video
description: Look at an attached video (MP4, WebM, MOV, MKV) and answer about what is shown in it. Use when the user asks what happens in a video, to summarize it, make notes or an outline of a lecture or presentation from its slides, find the moment where something appears, explain a screen recording, read the text shown on screen, or break down a fast movement frame by frame. For the script or shot list of a short video (TikTok, Reels, ads) use video-script; for saving frames as files use extract-video-frames.
---

# Understand a video

For exact, frame-accurate answers, `scripts/make_package.py` turns the video into a compact package: one key frame per scene (repeated scenes and transitions removed), a contact sheet with all frames and their times, and `index.md` with the scene list. Then you look at the package and answer.

## 1. Build the package

```bash
python3 <skill_dir>/scripts/make_package.py "<video path>" --out <output dir>
```

**Time limit.** Processing takes roughly a third to a half of the video's length for phone video (less for screen recordings). One code run is limited to about 5 minutes. For a video longer than about 7 minutes, process it in parts with `--start/--end` (for example 0:00–6:00, then 6:00–12:00), one part per run, and combine what you see.

Options, only when needed:
- `--start 1:00 --end 5:00`: the user asks about part of the video
- `--max-frames 60`: long or detailed video and the user wants detail (default 40, max 120)
- `--sensitivity high`: slides or screen recordings with small changes; `low` for shaky phone video with many false cuts

**Dense mode** (`--every SECONDS`): one frame every N seconds, all kept in time order, contact sheets split into pages (`contact_sheet_01.jpg`, `_02`, ...), times with hundredths of a second. At most 240 frames, so pick the step or the part to fit. Use it when the default key frames are not enough:
- **On-screen text or subtitles, line by line** (for example "what does the text in this clip say"): `--every 0.5` for videos up to 2 minutes. Read the pages in order and write out every line once, with its time. Write times as minutes:seconds the way the labels show them (`0:03.5`, `0:41`), never as `3:30` for 3.5 seconds. If the user wants a full script or shot list of a short video, the video-script skill gives that format.
- **Fast movement frame by frame** (a sports move, a dance step, a speedcube solve): `--every 0.033` (every frame at 30 fps) on a short part, for example `--start 0:10 --end 0:16`. Describe what changes between frames and when. Be honest about limits: motion blur and small details may hide exact moves.

The script prints JSON with `index`, `contact_sheet` (or `contact_sheets` in dense mode), `scenes`, `est_tokens`, or `error`.

## 2. Look, in this order

1. Read `contact_sheet.jpg`: all key frames with `#number  time` labels. This is usually enough for a summary.
2. Read `index.md` for exact scene times.
3. Open single frames from `frames/` only where you need detail: small text on a slide, a UI element, a face, a number.

Do not open every frame when the contact sheet answers the question.

## 3. Answer

- Answer the user's question directly. Refer to moments by time (`at 3:15`) so the user can jump there.
- For notes from a lecture or slides, follow the order of the scenes and quote slide text you can read.
- The package has **pictures only, no sound or speech**. If the answer depends on what is said and this environment has an audio transcription tool, use it too and match what is said to the frame times. Otherwise tell the user in one sentence and answer from what is visible. Burned-in subtitles are often the best substitute: use dense mode to read them.
- On `error`, explain it in plain words (for example, convert the file to MP4 H.264 and try again).
- Offer the ZIP (`zip` in the JSON) only if the user wants the frames themselves.
