# Copyright (C) 2025-2026 easyaspi314
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
import queue
import logging
from pathlib import Path
from collections import deque
import datetime
from datetime import timezone
from threading import Lock, Thread, Condition
from time import sleep
import uuid
import json
import math

import numpy as np
import onnxruntime as ort
import cachetools
from piper import PiperVoice
from piper.util import audio_float_to_int16
import psutil
from miniaudio import convert_frames, SampleFormat

import config
import event

from voice_manager import vm

@dataclass
class MessageInfo:
    message: str                # Message
    timestamp: str              # Timestamp
    voice: str                  # Voice to use
    skip: bool                  # Whether to skip this entry
    censor: bool                # Whether to censor bad words for future use
    sender: dict                # for future additions
    id: str                     # Unique UUID
    parsed_data: bytearray|None # Parsed TTS data
    duration: float             # 
    def __str__(self):
        return json.dumps(self)

    def tts_event(self, event_type: str, speekaboo_exception: str|None = None):
        """
        Sends a WebsocketEvent with the MessageInfo filled in.
        """
        payload = {
            "id": self.id,
            "timestamp": self.timestamp,
            "text": self.message,
            "duration": self.duration or 0.0,
            "engineName": "Speekaboo Piper",
            "voiceName": config.config["voices"][self.voice]["model_name"],
            "pitch":0.0,
            "volume": 1.0,
            "rate": 0.0
        }
        if speekaboo_exception is not None:
            payload["speekaboo_exception"] = speekaboo_exception

        event.ws_event(
            "texttospeech",
            event_type,
            payload
        )

_parsing_queue: queue.Queue[MessageInfo] = queue.Queue()
_queue: deque[MessageInfo] = deque()

def add(message: str, voice: str, timestamp: datetime.datetime = datetime.datetime.now(), censor: bool = False):
    message = message.strip()
    if len(message) == 0 or not config.enabled:
        return

    msg_id = uuid.uuid4()
    msgtoadd = MessageInfo(
        message = message,
        timestamp = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        voice = voice,
        skip = False,
        censor = censor,
        sender = {},
        id = str(msg_id),
        parsed_data=None,
        duration=0.0
    )

    _parsing_queue.put(msgtoadd)

    msgtoadd.tts_event("textqueued")
 
    return str(msg_id)
    

def pop() -> MessageInfo|None:
    if len(_queue) > 0:
        return _queue.popleft()
    else:
        return None

def peek(idx: int = 0) -> MessageInfo | None:
    if len(_queue) > idx:
        return _queue[idx]
    else:
        return None

def num_items() -> int:
    return len(_queue)

def to_list() -> list[MessageInfo]:
    lst = list(_queue)
    return lst


def toggle_skip(message: MessageInfo):
    try:
        idx = _queue.index(message)
        _queue[idx].skip = not _queue[idx].skip
    except ValueError:
        pass

def clear():
    _queue.clear()

def set_onnx_limit(size: int):
    """ Set a limit for ONNX because if unchecked, ONNX _will_ use all your RAM """
    ort_arena_config = ort.OrtArenaCfg(size, -1, -1, -1)
    ort_memory_info = ort.OrtMemoryInfo(
        "Cpu",
        ort.OrtAllocatorType.ORT_ARENA_ALLOCATOR,
        0,
        ort.OrtMemType.DEFAULT
    )
    ort.create_and_register_allocator(ort_memory_info, ort_arena_config)


@cachetools.cached(cache=cachetools.LRUCache(maxsize = config.config["max_memory_usage"], getsizeof=lambda x: x[1]))
def get_voice_impl(voicepath: Path) -> tuple[PiperVoice, float]: # model, memory usage
    """
    Since these voices can take up a lot of memory but also take a lot of time to load,
    we use cachetools to make a least 
    """
    logging.info("Loading voice %s", voicepath.stem)

    event.loading_voice(voicepath.stem)
    proc = psutil.Process()
    # estimate memory usage, since python doesn't manage the memory
    start_memory_usage = proc.memory_info().rss

    voice = PiperVoice.load(voicepath, use_cuda=config.config["use_cuda"], num_threads=config.config["num_threads"])

    end_memory_usage = proc.memory_info().rss
    diff_in_mb = (end_memory_usage - start_memory_usage) / (1024.0 * 1024.0)
    logging.info("Estimated memory usage: %.2f MiB", diff_in_mb)

    event.loaded_voice(voicepath.stem, diff_in_mb)
    return (voice, diff_in_mb)

def get_voice(voicepath: Path) -> PiperVoice:
    return get_voice_impl(voicepath)[0]

class TTSThread(Thread):
    def __init__(self):
        super().__init__(name="TTS Parsing Thread")
        self.queue = queue.Queue()
        self.running = False

    def parse_tts(self, message: MessageInfo):

        from audio import audio

        try:
            if message.voice not in config.config["voices"]:
                raise ValueError(f"Invalid voice {message.voice}")

            voice_info = config.config["voices"][message.voice]

            if voice_info.get("model_name", "") == "":
                raise ValueError(f"Voice alias {message.voice} doesn't have a name assigned!")

            voice_path = vm.get_voice_path(voice_info["model_name"])
            if voice_path is None:
                raise ValueError(f"Cannot find voice path for {voice_info['model_name']}")

            voice = get_voice(voice_path)

            logging.info("Speaker ID: %d", voice_info.get("speaker_id", 0))

            raw_pcms = []

            volume = voice_info["volume"]

            num_words = len(message.message.split())

            if config.config["max_words"] > 0 and num_words > config.config["max_words"]:
                raise OverflowError("Text is longer than word limit")

            for sentence in voice.synthesize_stream_raw(message.message,
                    speaker_id=voice_info.get("speaker_id", 0),
                    length_scale=voice_info.get("length_scale", 1.0),
                    noise_scale=voice_info.get("noise_scale", 0.667),
                    noise_w=voice_info.get("noise_w", 0.8),
                    max_words=config.config["max_words"]
                    ):
                # Adjust the volume
                if abs(volume - 1.0) > 0.01: # volume != 1.0

                    # Convert back to Signed16 (annoyingly, Piper converts from float to int16 beforehand)
                    le16 = np.dtype(np.int16).newbyteorder('<')
                    buf = np.frombuffer(sentence, le16)

                    # Normalize the volume for a more natural curve
                    # https://stackoverflow.com/a/1165188
                    # 32 seems to feel good.
                    normalized_vol = max(0.001, min((math.pow(32.0, volume) - 1) / (32.0 - 1), 1.0))
                    # Multiply by the normalized volume and convert back to LE16
                    buf = audio_float_to_int16(buf, min(32767.0 * normalized_vol, 32767.0)) # piper/util.py
                    # Convert to bytes
                    sentence = buf.tobytes()

                raw_pcms.append(sentence)

            # Join into a raw buffer
            wav_data = b''.join(raw_pcms)

            # Now convert the sample rate to the native rate.
            converted = convert_frames(SampleFormat.SIGNED16,
                                       from_numchannels=1,
                                       from_samplerate=voice.config.sample_rate,
                                       sourcedata=wav_data,
                                       to_fmt = SampleFormat.SIGNED16,
                                       to_numchannels=1,
                                       to_samplerate=audio.get_sample_rate())

            # Get the duration in milliseconds
            message.duration = round(len(converted) / 2 / audio.get_sample_rate() * 1000, 2)

            # Emit an event to signal that we processed it
            message.tts_event("engineprocessed")

            return converted
        except OverflowError:
            message.tts_event("error", "Message too long")
            return None
        except Exception as e: # pylint:disable=broad-exception-caught
            logging.error("Exception in parse_tts:", exc_info=e)
            message.tts_event("error", e.args[0])

            return None


    def stop(self):
        self.running = False
        if not self.is_alive():
            return

        self.join()
        logging.info("Joined TTS thread")

    def run(self):
        self.running = True
        set_onnx_limit(config.config.get("onnx_memory_limit", 1024) * 1024 * 1024)

        while self.running:
            while _parsing_queue.qsize() == 0 and self.running:
                sleep(0.5)
            if self.running:
                message = _parsing_queue.get()

                message.parsed_data = self.parse_tts(message)
                
                _parsing_queue.task_done()
                if message.parsed_data is None:
                    continue
                _queue.append(message)

        logging.info("Done running TTS thread")

tts_thread = TTSThread()
