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

import config
import miniaudio
import tts
import time
import threading
import logging
import queue

class AudioThread(threading.Thread):
    """
    Handles audio playback.

    Audio playback uses miniaudio.

    This is super messy.
    """
    busy = False
    device = None 

    def __init__(self):
        """
        Constructor
        """
        super().__init__()
        self.queue = queue.Queue()
        self.condition = threading.Condition()
        self.playing = False

    def get_devices() -> dict:
        """
        Gets a list of devices in a more friendly format than miniaudio:
        """
        devices = miniaudio.Devices()
        output = {}
        playbacks = devices.get_playbacks()
        for d in enumerate(playbacks, 1):
            if d[1]["name"] in output:
                print("warning: {} duplicated".format(d[1]["name"]))
            output[d[1]["name"]] = (d[0], d[1])
                
        return output
    
    def get_sample_rate(self):
        if self.device is None:
           self.init()

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
            self.playing = False
            self.condition.notify_all()

    def init(self):
        if self.device is not None:
            self.device.stop()
            self.device.close()
            
        self.device = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16,
                                               nchannels=1, app_name="Speekaboo")


    def stream_end_callback(self):
        logging.info("Stream end callback!")
        with self.condition:
            self.playing = False
            self.condition.notify_all()

    def run(self):
        """
        Audio thread entrypoint

        TODO: this needs some massive cleanup.
        """

        self.running = True
        self.init()
        while self.running:
            from server import ws_thread

            # todo: make this a condition variable
            while self.running and (len(tts._queue) == 0 or self.playing):
                time.sleep(0.5)

            while len(tts._queue) > 0 and self.running:

                message: tts.MessageInfo = tts.peek()
                if message is None or message.parsed_data is None:
                    break

                message = tts.pop()

                ws_thread.send_event("texttospeech", "playing", {
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
                    while self.playing:
                        self.condition.wait()
                
                ws_thread.send_event("texttospeech", "finished", {
                    "id": message.id,
                    "timestamp": message.timestamp,
                    "text": message.message,
                    "voiceName": config.config["voices"][message.voice].get("model_name", ""), 
                    "voiceEngine": "Speekaboo Piper",
                    "duration": len(message.parsed_data) / self.get_sample_rate() / 2 * 1000,
                    "volume": 1.0,
                    "rate": 0.0
                })

        logging.info("Closing audio thread")

    def stop(self):
        with self.condition:
            self.running = False
            self.condition.notify_all()
        self.device.close()
        self.join()

audio = AudioThread()