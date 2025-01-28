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

"""
Manages installed Piper voices.

TODO:
 - Allow adding custom voices
 - Do the downloads myself so we can have progress bars and such
 - Put on its own thread
"""
import config
import time
from pathlib import Path
from piper import download as PiperDownloader
import threading

class VoiceManager:
    def __init__(self):
        if config.data_folder is None:
            raise Exception("No data folder found!")
        
        voices_file = config.data_folder / "voices.json"
        # Update daily
        needs_update = not voices_file.exists() or time.time() - voices_file.stat().st_mtime > (60 * 60 * 24)
        try:
            self.voices = PiperDownloader.get_voices(config.data_folder, needs_update)
        except:
            self.voices = PiperDownloader.get_voices(config.data_folder, False)
            print("Couldn't parse downloads!")
        self.language = config.config["voice_language"]
        self.threads = dict()

    # wait for cleanup
    def wait_for_downloads(self):
        notified = False
        for thread in self.threads:
            if self.threads[thread].is_alive():
                if not notified:
                    notified = True
                    print("Waiting for downloads to complete...")
                self.threads[thread].join()
        self.threads = dict()

    def __del__(self):
        self.wait_for_downloads()

    def get_voices(self):
        return self.voices

    def is_voice_installed(self, voice: str) -> bool:
        try:
            PiperDownloader.find_voice(voice, [config.data_folder])
            return True
        except:
            return False

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
                except:
                    pass
                print(voice)

    def download_thread(self, voice: str, callback = None):
        result = False
        try:
            PiperDownloader.ensure_voice_exists(voice, [config.data_folder], config.data_folder, self.voices)
            result = True
        except:
            result = False
        print("Done downloading {} with result {}".format(voice, result))
        if callback is not None:
            callback(voice, result)

    def install_voice(self, voice: str, callback=None) -> bool:
        """
        Installs a voice on a separate thread, calling callback when complete.
        """
        if self.is_voice_installed(voice):
            if callback is not None:
                callback(voice, True)
    
        if voice in self.threads and self.threads[voice].is_alive():
            # be patient!!
            return

        voice = voice
        callback = callback

        self.threads[voice] = threading.Thread(target=self.download_thread, args=[voice, callback])
        self.threads[voice].start()

    def uninstall_voice(self, voice: str):
        try:
            onnx_path, config_path = PiperDownloader.find_voice(voice, [config.data_folder])
            Path(onnx_path).unlink()
            Path(config_path).unlink()
        except:
            pass
