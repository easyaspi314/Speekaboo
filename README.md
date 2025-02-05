# Speekaboo

Speekaboo is a WIP [Speaker.bot](https://speaker.bot) API implementation using the [Piper](https://github.com/rhasspy/piper)
text-to-speech library.

This was designed because on Linux, while Speaker.bot launches with the correct libraries, Sapi5 doesn't work (it's a stub
in Wine), Azure doesn't work, Google Cloud TTS has a weird popping, and basically everything else costs money.

While Speekaboo doesn't have chat integration (as of writing), it supports the same Websockets and UDP API as Speaker.bot, so
it can be integrated with other programs like Streamer.bot.

## Features

Speekaboo is far from complete. For basic functionality, it works good enough to use for a basic TTS bot.
For an EN-US voice, I recommend Amy Medium.

- [ ] Not spaghetti codebase
- [ ] Setup wizard (you need to manually add voices)
- [ ] Functional UI (half the things don't work lol)
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
  - [ ] Multiple/random voices (each voice alias is one voice only)
  - [ ] Speaker IDs (untested)
  - [ ] Pitch shift
  - [ ] Volume
  - [ ] Arabic support. piper-phonemize-cross does not include Tashkeel.
- [x] Downloading/uninstalling new voices
- [x] Adding custom .onnx voices
- [x] Manually playing text
- [ ] Profanity filter
- [ ] Interface to cancel or review messages
- [ ] Random voices/multiple voice aliases (todo, needs proper memory overhead management)
- [ ] In-GUI configuration
  - [x] Creating aliases
- [ ] Chat integration (NOT PLANNED, Streamer.bot can send commands)

## Installation

Requirements:

- Python >= 3.12 (lower versions may work)
- [Poetry](https://python-poetry.org)
- [pipx](https://pipx.pypa.io/)

```shell
poetry build
pipx install dist/*.whl
```

## Running

A desktop shortcut may be added in the future.

```shell
speekaboo
```

## Initial setup

As the program is far from completion, the setup step is not as straightforward as I want it to be,
mostly since I need to lay down the framework for dynamically updating the GUI.

1. Launch the program
2. Go to Download Voices, and select a voice. For English (US) I find Amy Medium (en_US-amy-medium) to be a good choice.
3. Click "Install/uninstall selected voice"
4. Restart the program.
5. Go to the Voice Aliases tab, and click "Add new alias", and pick a name
6. Pick the voice name in the Voice dropdown
7. Click "Save changes"
8. Restart the program again.
9. Pick the new name in the dropdown, enter some text, and hit enter!
