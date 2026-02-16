# Speekaboo

Speekaboo is an offline text-to-speech program that communicates using the [Speaker.bot](https://speaker.bot) API.
It uses a customized version of [Piper](https://github.com/rhasspy/piper) as the text-to-speech engine.

It is intended to be controlled by external programs like [Streamer.bot](https://streamer.bot).

This was designed because on Linux, while Speaker.bot launches with the correct libraries, Sapi5 doesn't work (it's a stub
in Wine), Azure doesn't work, Google Cloud TTS has a weird popping, and basically everything else costs money.

## Features

Speekaboo is far from complete. For basic functionality, it works good enough to use for a basic TTS bot.
For an EN-US voice, I recommend Amy Medium.

- [ ] Not spaghetti codebase
- [ ] Setup wizard (you need to manually add voices)
- [x] Functional UI
- [ ] Good UI
- [ ] Compatibility of the Speaker.bot WS/UDP API
  - [x] Basic speaking functionality
  - [x] Speak requests
  - [x] Speaking subscriptions (needed for Streamer.bot)
  - [x] Other subscriptions
  - [x] Compatibility with Streamer.bot
  - [ ] Document all functions and events
  - [ ] 100% API compatibility (some things are stubbed)
  - [ ] Proper error checking
- [ ] Playing voices
  - [x] Basic TTS
  - [x] Voice customization
  - [x] Speaker IDs
  - [ ] Pitch shift
  - [x] Volume
- [x] Downloading/uninstalling new voices
- [x] Adding custom .onnx voices
- [x] Manually playing text
- [ ] Denial-of-service prevention
  - [x] Stop button stops playback
  - [x] Stop button stops TTS processing
  - [x] Word limit (partial, doesn't include reading out special characters)
  - [x] CPU thread limits
  - [x] Memory usage limits
  - [x] Sentence splitting (long sentences drastically increase memory usage)
  - [ ] Processing/playback time limits
- [x] In-GUI configuration
  - [x] Creating aliases

The following features are outside of the scope of this program:

- Support for cloud-based TTS engines
  - These APIs are complicated or paid
  - Some of them still work in Speaker.bot via Wine
- Chat or other service integrations
  - Use external programs
- Any other online features outside of downloading voices
  - Use external programs
- Random voice selection
  - Use external programs
  - Note that while you can use multiple voice profiles, loading a voice takes a few seconds
    and the voice models take about 100 MiB RAM each. Speekaboo does keep a cache of the most
    recent voices though, the size of which can be configured.
  - It may be possible to randomize speaker IDs which doesn't require a reload, but that is a
    very niche feature.
- Support for platform-specific TTS engines
  - Speekaboo was designed to be cross-platform
- Chat censoring and other advanced moderation tools
  - Use external programs
  - A basic queue system is included
- Screen reader support
  - There are better programs
- Optimizations for reading long paragraphs
  - The Speaker.bot subscription API isn't designed around streaming, even though Piper is.
  - Most chat messages are short
  - Denial-of-service prevention features are welcome.

## Installation

Requirements:

- Python 3.10-3.14
- [Poetry](https://python-poetry.org) (uv and plain pip also work)

```shell
poetry install
```

## Running

A desktop shortcut may be added in the future.

```shell
speekaboo
```

## Initial setup

1. Launch the program
2. Go to Download Voices, and select a voice. For English (US) I find Amy Medium (en_US-amy-medium) to be a good choice.
3. Click "Install/uninstall selected voice"
4. Go to the Voice Aliases tab, and click "Add new alias", and pick a name
5. Pick the voice name in the Voice dropdown
6. Click "Save changes"
7. Pick the new name in the dropdown, enter some text, and hit enter!

## Notice

Copyright (c) 2025-2026 easyaspi314
Released under the MIT License.

This project includes code from the original version of Piper TTS, which is Copyright (c) 2022 Michael Hansen, also
released under the MIT License.

Speekaboo is not affiliated with Speaker.bot or Streamer.bot in any way.

Speekaboo has been written exclusively using [clean-room design](https://en.wikipedia.org/wiki/Clean-room_design) to
reverse engineer undocumented parts of the Speaker.bot API. It contains no copyrighted code or assets from any of
Streamer.bot's projects (including Speaker.bot), outside of including parts of the public API documentation which can
be rewritten on request. See CONTRIBUTING.md.
