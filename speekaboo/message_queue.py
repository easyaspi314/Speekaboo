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
from threading import Lock 
import uuid
import json

@dataclass
class MessageInfo:
    message: str        # Message
    timestamp: str      # Timestamp
    voice: str          # Voice to use
    skip: bool          # Whether to skip this entry
    censor: bool        # Whether to censor bad words for future use
    sender: dict        # for future additions
    id: str             # Unique UUID
    def __str__(self):
        return json.dumps(self)

_lock: Lock = Lock()
_queue: deque[MessageInfo] = deque()

def add(message: str, voice: str = config["default_voice"], timestamp: datetime.datetime = datetime.time(), censor: bool = False):
    
    message = message.strip()
    if len(message) == 0:
        return
    with _lock:
        _queue.append(MessageInfo(
            message = message,
            timestamp = timestamp.isoformat(),
            voice = voice,
            skip = False,
            censor = censor,
            sender = {},
            id = str(uuid.uuid4())
        ))

def pop() -> MessageInfo|None:
    with _lock:
        if len(_queue) > 0:
            return _queue.pop()
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

