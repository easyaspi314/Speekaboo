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
import json
from collections import deque
from piper import PiperVoice, download as PiperDownloader
import message_queue
import time
"""
Handles TTS and audio playback.

Audio playback uses miniaudio
"""

current_sample_rate: int = -1
current_device: str = ""

voice_data = deque()

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
busy = False
def stream_pcm(source):
    required_frames = yield b""  # generator initialization
    idx = 0
    busy = True
    while idx < len(source) and config.running:
        required_bytes = required_frames * 1 * 2
        sample_data = source[idx:idx+required_bytes]
        idx += required_bytes
        if not sample_data:
            break
        print(".", end="", flush=True)
        required_frames = yield sample_data

    busy = False
    
device = None 

voices: dict[str, PiperVoice] = {}

def play_tts(sentence, voice):
    try:
        onnx, cfg = PiperDownloader.find_voice(voice, [config.data_folder])

        if not voice in voices:
            voices[voice] = PiperVoice.load(onnx, cfg, False)
        print("Synthesizing...")
        bytearr = b""
        for sentence in voices[voice].synthesize_stream_raw(sentence):
            print(sentence)
            bytearr += sentence
        print("Done")
        # print(bytearr)
        stream = stream_pcm(bytearr)
        next(stream)
        device.start(stream)

    except Exception as e:
        print("fail lmao")

def reinit(samplerate: int):
    if device is not None:
        device.close()
        device = None

    device = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16,
                                      nchannels=1, sample_rate=samplerate)
    
    

def start_thread():
    global device, busy
    device = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16,
                                      nchannels=1, sample_rate=22050)
    while config.running:
        if busy == False and message_queue.num_items() > 0:
            message = message_queue.pop()
            print(message.message)
            play_tts(message.message, "en_US-amy-medium")
        else:
            time.sleep(0.5)
    device.close()
    device = None

