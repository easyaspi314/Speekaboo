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

import os
import json
import logging
from typing import Callable
import sys
import getpass
import tkinter as tk
from tkinter import messagebox
import threading
from pathlib import Path
from appdirs import AppDirs
import psutil

# Set up some exception handlers. These are handled in gui.poll().
waiting_exceptions = {}

def exception_hook(exc: type, val: BaseException, tb, name="Main thread"):
    """
    Main exception hook
    """
    waiting_exceptions[name] = (exc, val, tb)
    logging.error("Received exception in %s!", name, exc_info=(exc, val, tb))

    censored = str(val).replace(getpass.getuser(), "$USER")
    try:
        messagebox.showerror(
            title="Exception!",
            message=f"Fatal exception in {name}:\n{exc.__name__}(\"{censored}\")"
        )
    except: # pylint:disable=bare-except
        pass
    # os._exit(0)

def thread_exception_hook(args):
    """
    Exception hook for a sub thread.
    """
    name = "Unknown Thread"
    if isinstance(args.thread, threading.Thread) and args.thread.name :
        name = args.thread.name or "Unknown Thread"
    else:
        name = "Unknown Thread"
    exception_hook(args.exc_type, args.exc_value, args.exc_traceback, name)

threading.excepthook = thread_exception_hook

# Global UUID for the program. Definitely generated randomly, definitely has no
# significance whatsoever :)
GLOBAL_UUID = "3243f6a8-885a-308d-3131-98a2e0370734"
running = True
paused = False
enabled = True
dirinfo = AppDirs("Speekaboo")


def try_create_folder(pathname: str|Path) -> Path:
    # Don't show the username on screen
    censored_path = str(pathname).replace(r'getpass.getuser()', "$USER", 1)
    path = Path(pathname)
    if not path.exists():
        try:
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror(message=f"Cannot create folder {censored_path}: {e.strerror}")
            path = None
            raise e

    elif not path.is_dir():
        
        messagebox.showerror(message=f"{censored_path} is not a directory!")
        logging.error("%s is not a directory!", path)
        path = None
        raise OSError("Config folder is not a directory!")

    return path

default_piper_options = {
    "noise_scale": 0.667,      # How varied the model is
    "length_scale": 1.0,       # How fast the TTS talks (lower = faster)
    "noise_w": 0.8,            # How varied the word length is
    "sentence_silence": 0.2,   # How long to pause between sentences
}

system_mem = psutil.virtual_memory().total // (1024 * 1024) # in MiB

config_folder = try_create_folder(dirinfo.user_config_dir)
data_folder = try_create_folder(Path(dirinfo.user_data_dir) / "voicedata")


def load_config():
    """
    Try to load the config file, in either:
    - C:\\Users\\<username>\\AppData\\Local\\Speekaboo\\Speekaboo.json
    - ~/.config/Speekaboo/Speekaboo.json
    - ~/Library/Application Support/Speekaboo/Speekaboo.json
    """
    default_config = {
        "ws_server_enabled": True,                        # Whether to enable the Websocket server
        "ws_server_addr": "127.0.0.1",                    # Address of the Websocket server
        "ws_server_port": 7580,                           # Port for the Websocket server. The documentation erroneously
                                                          #     lists the default port as 7680, but it's really 7580.
        "udp_server_enabled": True,                       # Whether to enable the UDP server
        "udp_server_addr": "0.0.0.0",                     # Address for the UDP server. Not configurable in Speaker.bot.
        "udp_server_port": 6669,                          # Port for the UDP server.
        "voice_language": "en_US",                        # Voice language
        "voices": {

        },
        "additional_voices": {},                          # Map of additional voices {"voice_name": "path/to/file.onnx"}
        "use_cuda": False,                                # Whether to use Cuda
        "output_device": None,                            # Audio output device (null = default)
        "volume": 1.0,                                    # Output volume
        "queue_delay": 0.0,                               # Delay before playing voices (to allow time for moderation)
        "max_words": 25,                                  # Maximum number of words
        "max_memory_usage": min(512, system_mem // 32),   # How much memory in MIB we use before purging old voices. Default to 512 MiB or 1/32 system memory.
        "text_replacement": "filtered"                    # neuro-sama reference :)
    }
    config_file_path = None

    if config_folder is not None:
        config_file_path = config_folder / "Speekaboo.json"


    if config_file_path is not None and config_file_path.is_file():
        try:
            with open(config_file_path, "r", encoding="utf-8") as cfgfile:
                tmpjson = json.load(cfgfile)
                return (config_file_path, default_config | tmpjson)
        except IOError as e:
            logging.error("Error reading config file: %s", e)
        except json.JSONDecodeError as e:
            logging.error("Error parsing config file: %s", e)

        return (None, default_config)

    # assume first use
    return (config_file_path, default_config)



config_file, config = load_config()

def save_config() -> bool:
    """
    Attempts to save the config file.
    
    Returns True on success.
    """

    try:
        if config_folder is not None:
            if "" in config["voices"]:
                del config["voices"][""]

            stringified = json.dumps(config, indent=4)

            with open(config_folder / "Speekaboo.json", "w", encoding="utf-8") as cfgfile:
                cfgfile.write(stringified)

            return True


    except IOError as e:
        logging.error("Error saving config file: %s", e)
    except (ValueError, TypeError, RecursionError) as e:
        logging.error("Error encoding config file! This is a bug!", exc_info=e)

    return False

stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [stdout_handler]
if config_folder:
    handlers.append(logging.FileHandler(config_folder / "Speekaboo.log"))

logging.basicConfig(level=logging.INFO, handlers=handlers)


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
