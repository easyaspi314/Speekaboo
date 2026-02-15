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

"""
Manages installed Piper voices.

TODO:
 - Allow adding custom voices
 - Do the downloads myself so we can have progress bars and such
 - Put on its own thread
"""

import time
from pathlib import Path
import logging
import threading
import uuid
import json

from piper import download as PiperDownloader

import event
import config
class VoiceManager:
    def __init__(self):
        if config.data_folder is None:
            raise FileNotFoundError("No data folder found!")
        
        voices_file = config.data_folder / "voices.json"
        # Update daily
        needs_update = not voices_file.exists() or time.time() - voices_file.stat().st_mtime > (60 * 60 * 24)
        try:
            self.voices = PiperDownloader.get_voices(config.data_folder, needs_update)
        except IOError:
            self.voices = PiperDownloader.get_voices(config.data_folder, False)
            logging.error("Couldn't parse downloads!")
        self.language = config.config["voice_language"]
        self.threads: dict[str, threading.Thread] = {}


    # wait for cleanup
    def wait_for_downloads(self):
        notified = False
        for thread in self.threads.values():
            if thread.is_alive():
                if not notified:
                    notified = True
                    print("Waiting for downloads to complete...")
                thread.join()
        self.threads.clear()

    def get_downloadable_voices(self):
        return self.voices
        
    def get_voice_path(self, voice: str):
        
        if voice in config.config["additional_voices"]:
            file = config.config["additional_voices"][voice]
            if Path(file).exists() and Path(file + ".json").exists():
                return Path(file)
        
        if config.data_folder is None:
            return None

        try:
            path = PiperDownloader.find_voice(voice, [config.data_folder])
            return path[0]
        except (IOError, ValueError):
            return None


    def is_voice_installed(self, voice: str) -> bool:
        return self.get_voice_path(voice) is not None
    
    def get_voice_size(self, voice: str) -> int:
        size = 0
        for i in self.voices[voice]["files"]:
            size += self.voices[voice]["files"][i]["size_bytes"]

        return size

    def print_all_voices(self):
        for voice in self.voices:
            print(voice)

    def print_all_voices_lang(self, lang: str):
        for voice in self.voices:
            if self.voices[voice]["language"]["code"] == lang:
                try:
                    PiperDownloader.find_voice(voice, [config.data_folder])
                    print("Installed: ", end="")
                except ValueError:
                    pass
                print(voice)

    def download_thread(self, voice: str):
        result = False
        try:
            PiperDownloader.ensure_voice_exists(voice, [config.data_folder], config.data_folder, self.voices)
            result = True
            event.voices_changed(voice, True)
            logging.info("Done downloading %s with result %s", voice, result)
        except Exception as e: # pylint: disable=broad-except
            logging.error("Failed to download %s!", exc_info=e)
            event.voices_changed(voice, False)
            result = False

    def install_voice(self, voice: str) -> None:
        """
        Installs a voice on a separate thread
        """
        if self.is_voice_installed(voice):
            return

        if voice in self.threads and self.threads[voice].is_alive():
            # be patient!!
            return

        self.threads[voice] = threading.Thread(
            target=self.download_thread,
            args=[voice],
            name=f"Download Thread [{voice}]"
        )
        self.threads[voice].start()
    
    def get_all_installed_voices(self):
        if config.data_folder is None:
            return

        for file in config.data_folder.rglob("*.onnx"):
            name = Path(file).stem
            if self.is_voice_installed(name):
                yield (name, file)

        for voice in config.config["additional_voices"]:
            file = config.config["additional_voices"][voice]
            if Path(file).exists() and Path(file + ".json").exists():
                
                yield (voice, Path(file))

    def get_voice_config(self, voice: str) -> dict | None:
        filename = None
        if voice in config.config["additional_voices"]:
            file = config.config["additional_voices"][voice]
            if Path(file).exists() and Path(file + ".json").exists():
                filename = file + ".json"

        if filename is None:
            try:
                _onnx_path, config_path = PiperDownloader.find_voice(voice, [config.data_folder])
                filename = config_path
            except ValueError:
                return None
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except IOError as e:
            logging.error("IO Error opening %s.", filename, exc_info=e)
            return None
        except json.JSONDecodeError as e:
            logging.error("JSON Error opening %s", filename, exc_info=e)
            return None


    def uninstall_voice(self, voice: str):
        if config.data_folder is None:
            return

        try:
            onnx_path, config_path = PiperDownloader.find_voice(voice, [config.data_folder])
            Path(onnx_path).unlink()
            Path(config_path).unlink()
            event.voices_changed(voice, False)
        except IOError as e:
            logging.info("error", exc_info=e)
            pass

    def register_voice(self, voice_path: str):
        if Path(voice_path).exists() and Path(voice_path + ".json").exists():
            voice = Path(voice_path).stem
            config.config["additional_voices"][voice] = voice_path
            event.voices_changed(voice, True)

        else:
            raise ValueError("Could not find config file {}".format(voice_path))

    def deregister_voice(self, voice: str):
        if voice in config.config["additional_voices"]:
            del config.config["additional_voices"][voice]
            event.voices_changed(voice, False)

    def get_used_aliases(self, voice: str) -> list[str]:
        used_aliases: list[str] = []
        for alias in config.config["voices"].values():
            if alias.get("model_name", "") == voice:
                used_aliases.append(voice)
        return used_aliases
    
    def update_alias(self, name: str, voice: str = "", speaker: int|None = None, noise_scale: float|None = None,
                     length_scale: float|None = None, noise_w: float|None = None, sentence_pause: float|None = None, pitch: float|None = None,
                     volume: float|None = None):

        if not name in config.config["voices"]:
            if voice is None:
                raise ValueError("Cannot update/register a new alias without a voice name!")

            config.config["voices"][name] = {
                "model_name": voice,
                "speaker_id": speaker or 0,
                "noise_scale": noise_scale if noise_scale is not None else 0.667,
                "length_scale": length_scale if length_scale is not None else 1.0,
                "noise_w": noise_w if noise_w is not None else 0.8,
                "sentence_pause": sentence_pause if sentence_pause is not None else 0.2, 
                "pitch": pitch if pitch is not None else 1.0,
                "volume": volume if volume is not None else 1.0,
                "uuid": str(uuid.uuid4())
            }
        else:
        
            if voice is not None:
                config.config["voices"][name]["model_name"] = voice
            
            if speaker is not None:
                config.config["voices"][name]["speaker_id"] = speaker

            if noise_scale is not None:
                config.config["voices"][name]["noise_scale"] = noise_scale

            if length_scale is not None:
                config.config["voices"][name]["length_scale"] = length_scale
            
            if noise_w is not None:
                config.config["voices"][name]["noise_w"] = noise_w
            
            if sentence_pause is not None:
                config.config["voices"][name]["sentence_pause"] = sentence_pause

            if volume is not None:
                config.config["voices"][name]["volume"] = volume

            if pitch is not None:
                config.config["voices"][name]["pitch"] = pitch

vm = VoiceManager()
