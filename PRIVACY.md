# Privacy policy: Video Frame Extractor plugin for ChatGPT

Last updated: October 21, 2026

This policy covers the Video Frame Extractor **plugin for ChatGPT** (this repository). The Chrome extension of the same name has its own policy at https://videoframes.app/privacy/.

## What the plugin reads

- Only the video file you attach to a conversation with ChatGPT, and only when you ask ChatGPT to work with it.
- From that video the plugin makes still frames, a contact sheet and a short text index (`index.md`). A video can show personal information (faces, names, emails on a screen recording); the plugin does not look for it, extract it or label it.

## Where it is processed

- Inside ChatGPT's own code sandbox for your conversation, by the Python scripts in this repository (ffmpeg, NumPy, Pillow).
- The scripts make no network requests. Nothing is sent to the developer or to any third party.

## What is stored

- The developer stores nothing and runs no server for this plugin.
- The frames and files the plugin creates stay in your conversation's sandbox and are handled under OpenAI's own terms and privacy policy, like any other file in a ChatGPT conversation.

## Analytics and tracking

- None. The plugin has no analytics, accounts, cookies or tracking.
- Links in the plugin's README and listing carry UTM tags so the developer's website and the Chrome Web Store can count visits that come from the plugin. That happens only if you click a link.

## Children

The plugin is not directed at children under 18.

## Contact

Questions or concerns: allenmagic888@gmail.com, or open an issue at https://github.com/allenmagic8888/video-frame-extractor-chatgpt/issues
