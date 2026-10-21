---
name: video-script
description: Break down a short video the user attached (TikTok, Reels, Shorts, an ad or promo, up to about 3 minutes) into its script - every on-screen caption or subtitle line with its time, what each shot shows, how fast it is cut, and how it is structured (hook, problem, solution, proof, call to action) - plus a shot list the user can follow to make their own version. Use when the user asks for the script, scenario, storyboard, shot list or a breakdown of how a short video or trend is made. For other questions about a video use understand-video; for saving frames as files use extract-video-frames.
---

# Script of a short video

`scripts/make_package.py` in dense mode takes a frame every half second and lays them out on contact-sheet pages with times. Burned-in subtitles and on-screen text are usually the spoken script, so you read them from the pages.

## 1. Build the package

```bash
python3 <skill_dir>/scripts/make_package.py "<video path>" --out <output dir> --every 0.5
```

- Videos longer than 2 minutes: use `--every` = video length in seconds / 230, rounded up to 0.1 (for a 3-minute video, `--every 0.8`). The script refuses more than 240 frames and tells you the smallest step that fits.
- Videos longer than about 3 minutes are not short videos: use understand-video instead.
- One code run is limited to about 5 minutes; a 3-minute video fits easily.

The script prints JSON with `contact_sheets` (pages in order), `index`, `frames`, or `error`.

## 2. Read

Read every contact sheet page in order (`contact_sheet_01.jpg`, `_02`, ...). Each frame is labelled `#number m:ss.cc`. Open a single frame from `frames/` only when text is too small to read on the page.

While reading, note:
- each new caption or on-screen text line, verbatim, and the time it first appears (write each line once even if it stays on screen for several frames)
- each new shot: what is shown, the action, the camera (close-up, wide, hand-held, screen recording, selfie)
- text or banners that stay on screen the whole time (price, promotion, account name) - list them once

## 3. Answer with these parts

1. **One-line summary**: what the video is and who it is for.
2. **Script table**: time | words (captions, verbatim, in the original language; add a translation column if the user writes in another language) | what is shown. Write times as `0:03.5` or `0:41`, never `3:30` for 3.5 seconds.
3. **Structure**: the parts with their time ranges, such as hook, problem, solution, proof or demo, offer, call to action.
4. **Pace**: number of shots, average shot length, where the cuts speed up or slow down.
5. **Shot list for your own version**: numbered shots with length, what to film and what to say, adapted to the user's product or idea if they gave one. Write new wording; do not copy someone else's script word for word as the user's own.

If this environment has an audio transcription tool, you may add the spoken words as an extra column, marked as speech. Otherwise state once, briefly: the words come from on-screen captions, so speech without captions, music and sound effects are not included.

On `error`, explain it in plain words (for example, convert to MP4 H.264, or analyse a shorter part with `--start/--end`).
