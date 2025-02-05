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

from dataclasses import dataclass
from config import config
from collections import deque
import datetime
from threading import Lock, Thread, Condition
import uuid
import json
import cachetools
from piper import PiperVoice
from piper import download as PiperDownloader
import psutil
import threading
import config
import time
import queue
import logging
from voice_manager import vm
from audio import audio
from pathlib import Path

@dataclass
class MessageInfo:
    message: str           # Message
    timestamp: str         # Timestamp
    voice: str             # Voice to use
    skip: bool             # Whether to skip this entry
    censor: bool           # Whether to censor bad words for future use
    sender: dict           # for future additions
    id: str                # Unique UUID
    parsed_data: bytearray # Parsed TTS data
    def __str__(self):
        return json.dumps(self)

_lock: Lock = Lock()
_parsing_queue: queue.Queue[MessageInfo] = queue.Queue()
_queue: deque[MessageInfo] = deque()
_condition: Condition = Condition()

def add(message: str, voice: str = "Amy", timestamp: datetime.datetime = datetime.datetime.now(), censor: bool = False):
    message = message.strip()
    if len(message) == 0:
        return
    
    with _condition:
        id = uuid.uuid4()
        msgtoadd = MessageInfo(
            message = message,
            timestamp = timestamp.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z"),
            voice = voice,
            skip = False,
            censor = censor,
            sender = {},
            id = str(id),
            parsed_data=None
        )
        
        _parsing_queue.put(msgtoadd)
        from server import ws_thread

        ws_thread.send_event(event_source="texttospeech", event_type="textqueued", data= {
                "id": msgtoadd.id,
                "timestamp": msgtoadd.timestamp,
                "text": message,
                "duration": 0.0,
                "engineName": "Speekaboo Piper",
                "voiceName": config.config["voices"][voice]["model_name"],
                "pitch":0.0,
                "volume": 1.0,
                "rate": 0.0
            })
        _condition.notify_all()
        return str(id)
    

def pop() -> MessageInfo|None:
    with _lock:
        if len(_queue) > 0:
            return _queue.pop()
        else:
            return None

def peek(idx: int = 0) -> MessageInfo | None:
    with _lock:
        if len(_queue) > idx:
            return _queue[idx]
        else:
            return None

def num_items() -> int:
    return len(_queue)

def to_list() -> list[MessageInfo]:
    with _lock:
        lst = [x for x in _queue]
        print(lst)

def toggle_skip(message: MessageInfo):
    with _lock:
        try:
            idx = _queue.index(message)
            _queue[idx].skip = not _queue[idx].skip
        except ValueError:
            pass

def clear():
    with _lock:
        _queue.clear()


@cachetools.cached(cache=cachetools.LRUCache(maxsize = 512, getsizeof=lambda x: x[1]))
def get_voice_impl(voicepath: str) -> tuple[PiperVoice, float]: # model, memory usage
    """
    Since these voices can take up a lot of memory but also take a lot of time to load,
    we use cachetools to make a least 
    """
    print("Loading voice {}".format(Path(voicepath).stem))
    proc = psutil.Process()
    # estimate memory usage, since python doesn't manage the memory
    start_memory_usage = proc.memory_info().rss
    voice = PiperVoice.load(voicepath)
    end_memory_usage = proc.memory_info().rss
    diff_in_mb = (end_memory_usage - start_memory_usage) / (1024.0 * 1024.0)
    print("Estimated memory usage: {} MiB".format(diff_in_mb))
    return (voice, diff_in_mb)

def get_voice(voicepath: str) -> PiperVoice:
    return get_voice_impl(voicepath)[0]

class TTSThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.running = False

    def parse_tts(self, message: MessageInfo):

        from server import ws_thread
        try:
            if not message.voice in config.config["voices"]:
                raise ValueError("Invalid voice {}".format(message.voice))
            
            voice_info = config.config["voices"][message.voice]
            voice_path = vm.get_voice_path(voice_info["model_name"])
            if voice_path == None:
                raise ValueError("Cannot find voice path for {}".format(voice_info["model_name"]))
            
            
            voice = get_voice(voice_path)

            print("Speaker ID: {}".format(voice_info.get("speaker_id", 0)))

            raw_pcms = []
            for sentence in voice.synthesize_stream_raw(message.message,
                    speaker_id=voice_info.get("speaker_id", 0),
                    length_scale=voice_info.get("length_scale", 1.0),
                    noise_scale=voice_info.get("noise_scale", 0.667)

                    ):
                raw_pcms.append(sentence)

            wav_data = b''.join(raw_pcms)

            from miniaudio import convert_frames, SampleFormat

            converted = convert_frames(SampleFormat.SIGNED16,
                                       from_numchannels=1,
                                       from_samplerate=voice.config.sample_rate,
                                       sourcedata=wav_data,
                                       to_fmt = SampleFormat.SIGNED16,
                                       to_numchannels=1,
                                       to_samplerate=audio.get_sample_rate())

            # I think this is correct?
            duration = len(converted) / audio.get_sample_rate() / 2 * 1000

            ws_thread.send_event(event_source="texttospeech", event_type="engineprocessed", data= {
                "id": message.id,
                "timestamp": message.timestamp,
                "text": message.message,
                "duration": duration,
                "engineName": "Speekaboo Piper",
                "voiceName": voice_info["model_name"],
                "pitch":0.0,
                "volume": 1.0,
                "rate": 0.0
            })
            return converted

        except Exception as e:
            logging.error(e, exc_info=True)
            return bytearray()
#        pass

    def stop(self):
        self.running = False
        with _condition:
            _condition.notify_all()

        self.join()
        print("Joined TTS thread")

    def run(self):
        # import pdb
        #pdb.set_trace(header="TTS thread")
        self.running = True
        while self.running:
            with _condition:
                while _parsing_queue.empty() and self.running:
                    _condition.wait()
                if self.running:
                    message = _parsing_queue.get()
                    message.parsed_data = self.parse_tts(message)
                    _parsing_queue.task_done()
                    with _lock:
                        _queue.append(message)
                
        print("Done running TTS thread")

tts_thread = TTSThread()
tts_thread.start()
            
