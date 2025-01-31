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

import json
from pathlib import Path
from appdirs import AppDirs
import uuid
import queue

# Global UUID for the program. Definitely generated randomly, definitely has no
# significance whatsoever :)
GLOBAL_UUID = "3243f6a8-885a-308d-3131-98a2e0370734"
messages = queue.Queue() # placeholder
running = True
paused = False
enabled = True
dirinfo = AppDirs("Speekaboo")

def try_create_folder(pathname: str|Path) -> Path|None:
    path = Path(pathname)
    if not path.exists():
        try:
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
        except:
            print("Error creating directory {}".format(pathname))
            path = None
    elif not path.is_dir():
        print("{} is not a directory!".format(pathname))
        path = None
    return path

default_piper_options = {
    "noise_scale": 0.667,      # How varied the model is
    "length_scale": 1.0,       # How fast the TTS talks (lower = faster)
    "noise_w": 0.8,            # How varied the word length is
    "sentence_silence": 0.2,   # How long to pause between sentences
}

"""
Default configuration.
"""
config = {
    "ws_server_enabled": True,                        # Whether to enable the Websocket server
    "ws_server_addr": "127.0.0.1",                    # Address of the Websocket server
    "ws_server_port": 7580,                           # Port for the Websocket server. The documentation erroneously
                                                      #     lists the default port as 7680, but it's really 7580.
    "udp_server_enabled": True,                       # Whether to enable the UDP server
    "udp_server_addr": "0.0.0.0",                     # Address for the UDP server. Not configurable in Speaker.bot.
    "udp_server_port": 6669,                          # Port for the UDP server.
    "voice_language": "en_US",                        # Voice language
    "default_voice": "Amy",                           # Default voice
    "voices": {
        "Amy": {                                         # Voice name
            "language": "en_US",                         # language of the voice
            "model_name": "en_US-amy-medium",            # name of the model, the name of the file without .onnx
            "piper_options": default_piper_options,      # default options for piper
            "downloaded": False,                         # whether the voice has been downloaded
            "path": None,                                # default to data_folder/model_name.onnx
            "speaker": 0,                                # ID of the speaker
            "sample_rate": -1,                           # -1 = default to model.json
            "uuid": ""                                   # UUID placeholder
        }
    },
    "additional_voices": [],                          # Array of paths to additional voices
    "use_cuda": False,                                # Whether to use Cuda
    "output_device": None,                            # Audio output device (null = default)
    "volume": 1.0,                                    # Output volume
    "queue_delay": 0.0,                               # Delay before playing voices (to allow time for moderation)
    "max_words": 25,                                  # Maximum number of words
}

def gen_voice_uuid(name: str, info: dict) -> str:
    summary = "{}@{}@{}@{}@{}".format(name, info["model_name"], json.dumps(info["piper_options"]), info["sample_rate"], info["speaker"])

    return str(uuid.uuid5(uuid.UUID(GLOBAL_UUID), summary))

config["voices"]["Amy"]["uuid"] = gen_voice_uuid("Amy", config["voices"]["Amy"])

config_folder = try_create_folder(dirinfo.user_config_dir)
data_folder = try_create_folder(Path(dirinfo.user_data_dir) / "voicedata")
config_file = None

if config_folder is not None:
    config_file = config_folder / "Speekaboo.json"


if config_file is not None and config_file.is_file():
    """
    Try to load the config file, in either:
        - C:\\Users\\<username>\\AppData\\Local\\Speekaboo\\Speekaboo.json
        - ~/.config/Speekaboo/Speekaboo.json
        - ~/Library/Application Support/Speekaboo/Speekaboo.json
    """
    try:
        with open(config_file, "r") as cfgfile:
            tmpjson = json.load(cfgfile)
            config = config | tmpjson
    except Exception as e:
        print("Error reading config file: {}".format(e))

def save_config() -> bool:
    """
    Attempts to save the config file.
    
    Returns True on success.
    """
    try:
        if config_file is not None:
            with open(config_file, "w") as cfgfile:
                json.dump(config, cfgfile)
                
            return True
        else:
            print("Config folder is not writeable, skipping.")
            return False
    except Exception as e:
        print("Error saving config file: {}".format(e))
        return False
