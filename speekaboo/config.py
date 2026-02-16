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

# 0/unset: normal operation
# 1: Logging set to debug
# 2+: Ctrl+C and exception handlers disabled
debug = int(os.getenv("SPEEKABOO_DEBUG") or "0")

if debug < 2:
    def exception_hook(exc: type, val: BaseException, tb, name="Main thread"):
        """
        Main exception hook
        """
        waiting_exceptions[name] = (exc, val, tb)
        logging.error("Received exception in %s!", name, exc_info=(exc, val, tb))

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

def join_or_die(thread: threading.Thread):
    """
    Like thread.join(), but handles timeouts and kills the program if it times out
    """
    try:
        # Wait 5 seconds
        thread.join(5)
    except RuntimeError: # 3.14+: PythonFinalizationError
        return

    if thread.is_alive():
        logging.error("Timeout when joining thread %s", thread.name)
        logging.shutdown()
        save_config()
        # kill everything
        os._exit(1)

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
cpu_count = psutil.cpu_count(logical=False) or 1

config_folder = try_create_folder(dirinfo.user_config_dir)
data_folder = try_create_folder(Path(dirinfo.user_data_dir) / "voicedata")


def load_config():
    """
    Try to load the config file, in either:
    - C:\\Users\\<username>\\AppData\\Local\\Speekaboo\\Speekaboo.json
    - ~/.config/Speekaboo/Speekaboo.json
    - ~/Library/Application Support/Speekaboo/Speekaboo.json
    """

    # Either half your physical cores (e.g. 2 threads on a 4c8t CPU) or 6 threads
    # There is no major benefit over 6 threads.
    preferred_threads = min(max(cpu_count // 2, 1), 6)

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
        "use_cuda": False,                                # Whether to use Cuda (currently disabled)
        "output_device": None,                            # Audio output device (null = default)
        "volume": 1.0,                                    # Output volume
        "queue_delay": 0.0,                               # Delay before playing voices (to allow time for moderation)
        "max_words": 100,                                 # Maximum number of words
        "max_memory_usage": min(512, system_mem // 32),   # Cache size. Default to 512 MiB or 1/32 system memory.
        "text_replacement": "filtered",                   # neuro-sama reference :)
        "num_threads": preferred_threads,                 # Number of threads for CPU inference
        "onnx_memory_limit": 1024,                        # Memory limit for ONNX
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

logging.basicConfig(level=logging.DEBUG if debug > 0 else logging.INFO, handlers=handlers)

