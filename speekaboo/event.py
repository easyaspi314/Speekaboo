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

import logging

# https://stackoverflow.com/a/27315715
class Observer():
    """
    Observer base class
    """
    observers = []
    def __init__(self):
        self.observers.append(self)
        self.observables: dict[str, Callable] = {}
    def observe(self, event_name, callback):
        self.observables[event_name] = callback


class Event():
    def __init__(self, name, *args, autofire = True):
        self.name = name
        self.args = args
        if autofire:
            self.fire()
    def fire(self):
        for observer in Observer.observers:
            if self.name in observer.observables:
                observer.observables[self.name](*self.args)

def ws_event(event_class: str, event_type: str, payload: dict):
    Event(
        "WebsocketEvent",
        event_class,
        event_type,
        payload
    )


def warn(message: str):
    logging.warning(message)
    ws_event(
        "internal_event",
        "warn",
        {
            "message": message
        }
    )

def info(message: str):
    logging.info(message)
    ws_event(
        "internal_event",
        "info",
        {
            "message": message
        }
    )

def loading_voice(voice_name: str):
    ws_event(
        "internal_event",
        "loading_voice",
        {
            "voice": voice_name
        }
    )

def loaded_voice(voice_name: str, size: float):
    ws_event(
        "internal_event",
        "loaded_voice",
        {
            "voice": voice_name,
            "mem": size
        }
    )

def voices_changed(voice: str, installed: bool):
    Event("voices_changed", voice, installed)
