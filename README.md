# Video Frame Extractor for ChatGPT: summarize videos, extract frames, get the script of any TikTok

**Can ChatGPT watch a video?** With this free plugin it can do it frame by frame. Attach an MP4, MOV or WebM and ChatGPT gets every scene or slide as a key frame with its exact time. It can then summarize the video, turn a lecture into notes, write out the script and shot list of a TikTok or ad, or save frames as JPG, PNG, ZIP or PDF.

- 🎬 **Scene detection** for slides, screen recordings, phone video, fast TikTok edits and talking heads with graphics
- ⏱️ **Exact timecodes** on every frame (`0:41`, `1:03.5`), so you can jump straight to the moment
- 📝 **TikTok, Reels and ad scripts**: every on-screen caption, read every 0.5 s, with a shot list for your own version
- 📄 **Video to PDF or ZIP**: one frame per slide, a frame every N seconds, or the frame at 1:23
- 🔒 **Private**: runs inside ChatGPT's own code sandbox; your video is not sent anywhere else
- 🆓 **Free and open source** (MIT)

## How to install the plugin in ChatGPT

1. **Download** [video-frame-extractor-chatgpt.zip](https://github.com/VideoFrameExtractorApp/video-frame-extractor-chatgpt/releases/latest/download/video-frame-extractor-chatgpt.zip) (latest release).
2. In ChatGPT open **Plugins**, then **Add** (top right) and **Upload plugin archive**. Choose the ZIP and click **Add plugin**.
3. Open the **Personal** tab and click **+** next to *Video Frame Extractor* to install it.

## How to use it

1. Start a new chat and attach your video.
2. Type `@Video Frame Extractor` and pick the plugin from the list.
3. Ask in your own words, for example:
   - "What is this video about? Short summary with times."
   - "Break down this TikTok: script, shots and a shot list for my product."
   - "Make a PDF with one frame for each slide of this lecture."

ChatGPT answers in a minute or two, with times you can click back to and files you can download.

Need frames from a video that only plays in your browser (YouTube, an online course, a webinar)? See [the Chrome extension](#need-more-the-chrome-extension) below.

## What it does

### Understand a video
- **Summarize**: "What is this video about?"
- **Notes from slides**: "Make an outline of this lecture from its slides"
- **Find a moment**: "When does the chart with sales appear?"
- **Explain a screen recording**: "What goes wrong in this recording?" Each new screen, window, panel or notification becomes its own frame
- **Fast movement frame by frame**: "Break down this move second by second" shows every frame of a short part with times to hundredths of a second

The plugin turns the video into a compact package: one key frame per scene, with repeated scenes and transitions removed, plus a contact sheet of all frames with their times. ChatGPT looks at the contact sheet first and opens single frames only when it needs detail. A 10-minute video usually costs a few thousand tokens instead of hundreds of thousands. Answers point to times (`at 3:15`).

The package has pictures only. When speech matters, ChatGPT can add its own audio transcription where available and match it to the frame times.

### Script of a short video
For TikTok, Reels, Shorts and ads up to about 3 minutes:
- **Script table**: every caption or on-screen text line, verbatim, with its time, next to what each shot shows
- **Structure and pace**: hook, problem, solution, proof, call to action; number of shots and average shot length
- **Shot list for your own version**: what to film and say, adapted to your product if you describe it

The words come from burned-in captions (the plugin reads a frame every 0.5 s); spoken words can be added as a separate column where ChatGPT can transcribe audio.

### Save frames
- **Frame at a specific time**: "give me the frame at 1:23"
- **Every N seconds**: "a picture every 5 seconds"
- **N frames across the video**: "20 stills from the whole video"
- **One frame per scene or slide**: "one picture for each slide of this lecture" (taken from the middle of each scene; fades and repeated slides are skipped)
- **Part of the video only**: "every scene between 0:30 and 2:00"
- **Formats**: JPG (default), PNG, WebP; bundled as a ZIP or a PDF with one picture per page
- File names include the timestamp, so you always know where a frame came from

Input: MP4, WebM, MOV, MKV and other formats ffmpeg can read. Up to 300 saved frames per request.

## Use cases

- **Summarize a video with ChatGPT**: lectures, webinars, product demos, meeting recordings
- **Lecture video to notes**: one section per slide, slide text quoted, times to jump back
- **Screen recording to steps**: what was clicked, which screen opened, where an error appeared (handy for bug reports and how-to guides)
- **TikTok, Reels and ad breakdown**: script, shots, pace, hook-problem-solution structure, a shot list for your own version
- **Video to images**: frames as PNG or JPG, slides from a video as one PDF, a contact sheet of the whole video
- **Frame-by-frame analysis**: a sports move, a dance step or any fast action, with times to hundredths of a second

## Example prompts

1. "What is this video about? Give me a short summary with times."
2. "Make notes from this lecture recording, one section per slide."
3. "Break down this TikTok: script, shots and structure, then a shot list for my own product."
4. "Extract one frame for every slide in this lecture and give me a PDF."
5. "Save a PNG of the frame at 0:42 from this clip."
6. "Give me 12 evenly spaced stills from this video as a ZIP."

## How it works

The plugin has three skills with small Python scripts that run ffmpeg in ChatGPT's code sandbox:

- Scene detection (`scenecut.py`) uses three detectors: whole-frame cuts (slides, film cuts), screen states for screen recordings (a window, panel or notification appears and stays; the mouse cursor is ignored), and view drift for phone and action-camera video (the camera has turned or moved to a different view).
- Before saving a key frame, `understand-video` compares it with 4 neighbours (±0.4 s, inside the same scene) and replaces it only if it is clearly blurred.
- `understand-video` (`make_package.py`): finds scene changes, takes one frame from the middle of each scene, merges scenes that look the same, splits very long scenes so nothing is missed, keeps at most 40 frames by default, and writes the frames, `contact_sheet.jpg` and `index.md`.
- `understand-video` dense mode (`--every`): a frame every N seconds in time order, contact sheets split into pages, times to hundredths of a second.
- `video-script`: the same `make_package.py` in dense mode (a frame every 0.5 s), read page by page for captions and shots.
- `extract-video-frames` (`extract_frames.py`): saves frames by time, interval, count or scene as image files, a ZIP or a PDF.

The scripts read only the video you attached and make no network requests of their own. They use ffmpeg, NumPy and Pillow, which ChatGPT's code sandbox already has; only where one is missing and package installs are allowed do they install it from PyPI. No data is collected.

## Troubleshooting

- **"Could not read this video"**: the file may be damaged or use an unusual codec. Convert it to MP4 (H.264) and try again.
- **Missed slide changes**: ask for "more detail", which raises scene sensitivity. For shaky phone video with too many frames, ask for "fewer".
- **Too many frames / large ZIP**: ask for JPG, a smaller width (e.g. 1280 px) or a shorter part of the video.

## Need more? The Chrome extension

The same developer makes **Video Frame Extractor** for Chrome, which adds what a chat can't do:

- **Videos you can't attach**: record a tab, window or screen and get frames from YouTube, online courses, webinars and other videos that play in the browser
- **Frame-by-frame by hand**: step with ← → and save exactly the moment you want
- **Quick capture**: screenshot the video area with a hotkey (Alt+Shift+S)
- **Everything stays on your device**: no upload, no size limit, original resolution up to 4K
- 52 languages, no account, no ads, no watermark

[Install from the Chrome Web Store](https://chromewebstore.google.com/detail/video-frame-extractor/mcmdhhpbgmkeggmfhclacdkhbdgohfak?utm_source=chatgpt&utm_medium=plugin&utm_campaign=readme) · [videoframes.app](https://videoframes.app/?utm_source=chatgpt&utm_medium=plugin&utm_campaign=readme)

## FAQ

**Can ChatGPT watch videos?**
ChatGPT can read images, not play video. This plugin turns the video into key frames with times, and ChatGPT reads those. For screen recordings, slides and fast edits that is more precise than sampling frames at random.

**How do I extract frames from a video in ChatGPT?**
Install the plugin, attach the video, mention `@Video Frame Extractor` and ask: "every scene as PNG in a ZIP", "a frame every 5 seconds" or "the frame at 0:42".

**Can it make a script from a TikTok or Reels video?**
Yes. It reads the burned-in captions every half second and lists each line with its time, next to what each shot shows. Then it gives the structure (hook, problem, solution, proof, call to action) and a shot list for your own version.

**Does it hear the sound?**
The frames carry no sound. Where ChatGPT can transcribe audio itself, it adds the spoken words next to the frame times. Otherwise it says so and works from what is on screen.

**Is my video uploaded anywhere?**
No. Everything runs in ChatGPT's code sandbox for your conversation, and the scripts make no network requests.

**Which formats and lengths work?**
MP4, MOV, WebM, MKV and anything else ffmpeg reads. Videos up to about 7 minutes are processed in one go. Longer videos are handled in parts.

**Is there a version for Claude?**
Yes: [Video Frame Extractor for Claude](https://github.com/allenmagic8888/video-frame-extractor-claude).

## Support and privacy

- Contact: allenmagic888@gmail.com
- Privacy policy (plugin): [PRIVACY.md](PRIVACY.md)
- Privacy policy (Chrome extension): https://videoframes.app/privacy/
- License: MIT
