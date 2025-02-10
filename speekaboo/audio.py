# Copyright (C) 2025 easyaspi314
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import time
import threading
import logging
import queue

import miniaudio

import config
import tts

class AudioThread(threading.Thread):
    """
    Handles audio playback.

    Audio playback uses miniaudio.

    This is super messy.
    """
    busy = False

    def __init__(self):
        """
        Constructor
        """
        super().__init__(name="Audio Thread")
        self.queue = queue.Queue()
        self.condition = threading.Condition()
        self.playing = False
        self.running = False
        self.device = None
        self.playback_devices = None


    def initialize(self):

        if self.device is not None:
            self.device.stop()
            self.device.close()
            self.device = None

        self.get_devices()
        assert self.playback_devices is not None

        wanted_device = config.config["output_device"]

        if wanted_device is not None and wanted_device in self.playback_devices:
            output_device = self.playback_devices[wanted_device][1]["id"]
        else:
            if wanted_device is not None:
                logging.warning("Selected audio device %s not found. Choosing the default.", wanted_device)
            output_device = None
        try:
            self.device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=1,
                app_name="Speekaboo",
                device_id=output_device
            )
        except miniaudio.MiniaudioError as e:
            config.Event("raise_error", f"MiniAudio error: {e.args[0]}", e)



    def get_devices(self) -> dict:
        """
        Gets a list of devices in a more friendly format than miniaudio:
        """
        if self.playback_devices is None:
            try:
                devices = miniaudio.Devices()
                self.playback_devices = {}
                playbacks = devices.get_playbacks()
                for d in enumerate(playbacks, 1):
                    if d[1]["name"] in self.playback_devices:
                        logging.warning("warning: %s duplicated", d[1]["name"])
                    self.playback_devices[d[1]["name"]] = (d[0], d[1])
            except miniaudio.MiniaudioError as e:
                logging.error("Error getting audio devices.", exc_info=e)
                self.playback_devices = {}

        return self.playback_devices

    def get_sample_rate(self):
        if self.device is None:
            return -1
        return self.device.sample_rate

    def stream_pcm(self, source):
        """
        https://github.com/irmen/pyminiaudio/blob/master/examples/demo3.py
        """
        required_frames = yield b""  # generator initialization
        idx = 0
        while idx < len(source) and config.running and self.playing:
            required_bytes = required_frames * 1 * 2
            sample_data = source[idx:idx+required_bytes]
            idx += required_bytes
            if not sample_data:
                break
            required_frames = yield sample_data



    def stop_playback(self):
        """
        Stops the active speaking voice
        """
        with self.condition:
            if self.playing and self.device is not None and self.device.running:
                self.device.stop()
            self.playing = False
            self.condition.notify_all()


    def stream_end_callback(self):
        with self.condition:
            self.playing = False
            self.condition.notify_all()

    def run(self):
        """
        Audio thread entrypoint

        TODO: this needs some massive cleanup.
        """
        assert self.device is not None

        self.running = True
        while self.running:

            # todo: make this a condition variable
            while self.running and (len(tts._queue) == 0 or self.playing):
                time.sleep(0.5)

            while len(tts._queue) > 0 and not config.paused and self.running:

                message = tts.peek()
                if message is None or message.parsed_data is None:
                    break

                tts.pop()

                config.Event(
                    "WebsocketEvent",
                    "texttospeech", "playing", {
                    "id": message.id,
                    "timestamp": message.timestamp,
                    "text": message.message,
                    "voiceName": config.config["voices"][message.voice].get("model_name", ""), 
                    "voiceEngine": "Speekaboo Piper",
                    "duration": len(message.parsed_data) / self.get_sample_rate() / 2 * 1000,
                    "volume": 1.0,
                    "rate": 0.0
                })
                # https://github.com/irmen/pyminiaudio/blob/master/examples/playcallbacks.py
                stream = self.stream_pcm(message.parsed_data)
                next(stream)
                callbacks_stream = miniaudio.stream_with_callbacks(stream, end_callback=self.stream_end_callback)
                next(callbacks_stream)
                self.playing = True
                self.device.start(callbacks_stream)

                # Wait for playback to finish
                with self.condition:
                    while self.playing and self.running:
                        print("Playing")
                        self.condition.wait()
                
                config.Event(
                    "WebsocketEvent",
                    "texttospeech",
                    "finished", {
                    "id": message.id,
                    "timestamp": message.timestamp,
                    "text": message.message,
                    "voiceName": config.config["voices"][message.voice].get("model_name", ""), 
                    "voiceEngine": "Speekaboo Piper",
                    "duration": len(message.parsed_data) / self.get_sample_rate() / 2 * 1000,
                    "volume": config.config["voices"][message.voice].get("volume", 1.0),
                    "rate": 0.0
                })

        logging.info("Closing audio thread")

    def stop(self):
        if not self.is_alive():
            return
        logging.info("Shutting down audio")
        self.stop_playback()
        self.running = False
        if self.device is not None:
            self.device.close()
        self.join()

audio = AudioThread()