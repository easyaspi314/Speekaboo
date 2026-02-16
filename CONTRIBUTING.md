# Contributing

Hello! Welcome to Speekaboo! While Speekaboo is a small project, contributions are always welcome!

The two main ways you can help are with bug reports and pull requests.

## Code of Conduct

- Keep all conversations respectful.
- Try to stay on topic.
- English is preferred.
- Follow the clean-room guidelines below.

## Bug Reports

Before making a bug report, make sure to search for the issue you're having to see if it hasn't
been reported before.

If you're certain the bug hasn't been reported, go ahead and report it!

When making a bug report, first make sure to give the following info:

- A description of the bug (don't just say "it's not working")
- Your OS
- The Python version you are using
- The Speekaboo version/commit you are using
- Any settings you changed from the default
- If applicable, attach a log. It should be found in one of these locations. You may need to show hidden files.
  - Windows (Normal install): `%LOCALAPPDATA%\Speekaboo\Speekaboo.log`
  - Windows (Microsoft Store): `%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.<version>_<gibberish>\LocalCache\Local\Speekaboo\Speekaboo.log`
  - Linux, FreeBSD, etc: `~/.config/Speekaboo/Speekaboo.log`
  - macOS: `~/Library/Application Support/Speekaboo/Speekaboo.log`

Then, try to narrow down the fewest steps you can reproduce the issue. If you can't reproduce it, recall what you remember happening.

## Feature requests and scope

Feature requests are always welcome, but please search to see if it hasn't been requested before.

Open an issue an make sure to put `[FEATURE]` in the title of your feature request, and describe
exactly what feature you want and why you think it should be added

Please keep in mind that Speekaboo is **not** a 1:1 replacement for Speaker.bot. Check README.md
for a list of explicitly out-of-scope features.

## Localization

Localization support is planned in the future once the main feature set is complete.

## Pull requests

If you would like to make a pull request, please adhere to the following guidelines:

- Make the changes as small and targeted as possible. Make multiple pull requests if you need to.
- Explain what the pull request changes.
- If the code isn't obvious, document it.
- Follow basic code style. Just don't make things any uglier.
- AI-generated code is strictly prohibited.
- Ensure all code is compatible with the MIT License.
- Please give credit for any code snippets you didn't write. 

## Clean room guidelines

Speekaboo has been written exclusively using [clean-room design](https://en.wikipedia.org/wiki/Clean-room_design) to
reverse engineer undocumented parts of the Speaker.bot API. It contains no copyrighted code or assets from any of
Streamer.bot's projects (including Speaker.bot), outside of including parts of the public API documentation which can
be rewritten on request.

These are the only techniques used:

- Reading public API documentation
- Reading open source projects
- Intercepting network traffic
- Black box testing

Please refrain from contributing to the project if you have:

- Disassembled or decompiled any of Streamer.bot's projects
- Accessed the source code or private documentation of any of Streamer.bot's proprietary projects
- Any other insider knowledge about Streamer.bot's projects
