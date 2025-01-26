# Speekaboo

Speekaboo is a WIP [Speaker.bot](https://speaker.bot) API implementation using the [Piper](https://github.com/rhasspy/piper)
text-to-speech library.

This was designed because on Linux, while Speaker.bot launches with the correct libraries, Sapi5 doesn't work (it's a stub
in Wine), Azure doesn't work, Google Cloud TTS has a weird popping, and basically everything else costs money.

While Speekaboo doesn't have chat integration (as of writing), it supports the same Websockets and UDP API as Speaker.bot, so
it can be integrated with other programs like Streamer.bot. 
