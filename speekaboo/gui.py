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
import logging
import sys
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [stdout_handler]
if config.config_folder:
    handlers.append(logging.FileHandler(config.config_folder / "Speekaboo.log"))
                 

logging.basicConfig(level=logging.INFO, handlers=handlers)

import signal
import tkinter as tk
import tkinter.filedialog

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.dialogs import Messagebox, Querybox

from server import ws_thread, udp_thread
from voice_manager import vm
import math
import audio
import tts

audio.audio.start()

window = ttk.Window()
window.geometry("600x400")
window.title("Speekaboo")

notebook = ttk.Notebook(window)
notebook.pack(expand=True, fill="both", padx=5, pady=5)

# DEBUG: always uses this
# vm.install_voice("en_US-amy-medium")

def do_close():
    if not config.running:
        return
    config.running = False
    global window
    print("Waiting for downloads")
    vm.wait_for_downloads()
    audio.audio.stop()
    ws_thread.stop()
    udp_thread.stop()
    tts.tts_thread.stop()
    config.save_config()

    if window is not None:
        window.destroy()
        window = None
    sys.exit(0)

class MainTab(ttk.Frame):
    def manual_send(self, event=None):
        if len(config.config["voices"]) == 0:
            Messagebox.show_error("Before you can use the TTS, download a voice in the Voices tab and then create a Voice Alias!")
            return
        msg = self.manual_text.get()
        voice = self.alias_select.get()
        if len(voice) == 0:
            Messagebox.show_error(parent=self, message="Please select a voice")
            return
        self.manual_text.delete(0, tk.END)

        tts.add(msg, voice)


    """
    Main tab
    
    Contains:
       - Main controls
       - Log
       - Manual textbox
    """
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        row = 0
        ttk.Label(self, text="TTS Queue").grid(row=row, column=0, columnspan=5, sticky="nesw")
        row += 1
        self.log_box = ttk.Treeview(self, selectmode="browse", show=["tree"])
        self.log_box.grid(row=row, column=0, columnspan=5, sticky="nesw", padx=5, pady=5)
        self.log_box.insert("", 0, text="Test 1")
        self.log_box.insert("", 1, text="Test 2")
        self.log_box.insert("", 2, text="Test 3")
        self.grid_rowconfigure(row, weight=1)
        row += 1
        self.alias_select = ttk.Combobox(self, values=list(config.config["voices"].keys()), width=1, state=ttk.READONLY)
        self.alias_select.grid(row=row, column=0, sticky=ttk.NSEW, padx=5, pady=5)

        self.manual_text = ttk.Entry(self, text="hello")
        self.manual_text.grid(row=row, column=1, columnspan=3, sticky="nesw", padx=5, pady=5)
        self.manual_text.bind("<Return>", self.manual_send)
        self.play_button = ttk.Button(self, text="Speak", command=self.manual_send)
        self.play_button.grid(row=row, column=4, sticky="nesw", padx=5, pady=5)
        row += 1

        self.stop_button = ttk.Button(self, text="Stop", bootstyle="secondary", command=audio.audio.stop_playback)
        self.stop_button.grid(row=row, column=0, sticky="nesw", padx=5, pady=5)
        ToolTip(self.stop_button, text="Stop the currently playing message")
        self.pause_button = ttk.Button(self, text="Pause", bootstyle="secondary")
        self.pause_button.grid(row=row, column=1, sticky="nesw", padx=5, pady=5)
        ToolTip(self.pause_button, text="Pause/resume the queue.")
        self.disable_button = ttk.Button(self, text="Disable", bootstyle="secondary")
        self.disable_button.grid(row=row, column=2, sticky="nesw", padx=5, pady=5)
        ToolTip(self.disable_button, text="Enable/Disable queueing and playback")
        self.quit_button = ttk.Button(self, text="Clear", bootstyle="secondary", command=tts.clear)
        self.quit_button.grid(row=row, column=3, sticky="nesw", padx=5, pady=5)
        ToolTip(self.quit_button, text="Clears the queue")
        self.quit_button = ttk.Button(self, text="Quit", bootstyle="secondary", command=do_close)
        self.quit_button.grid(row=row, column=4, columnspan=2, sticky="nesw", padx=5, pady=5)
        ToolTip(self.quit_button, text="Quits the program")

        for i in range(4):
            self.grid_columnconfigure(i, weight=1)
        
        self.pack(expand=True, fill="both")

main_tab = MainTab(notebook)
notebook.add(main_tab, text="Main")

class VoiceAliasesTab(ttk.Frame):
    """
    Tab to manage voice aliases and custom voices
     _Aliases______________________________________
    |>voice 1<| Name: ____________________________ |
    | voice 2 | Voice: <name> <quality> <speaker>  |
    | voice 3 | Variation: ____                    |
    |         | Speed: ___         etc             |
    |         | Volume:                            |
    |---------'------------------------------------|
 
    """
    class VoiceConfigFrame(ttk.Frame):

        def load_voice(self, voice: str):
            self.grid(row=0, column=1, sticky=tk.NSEW)
            self.name_var.set(voice)
            self.voice_var.set(config.config["voices"][voice].get("model_name", ''))
            self.voice_name.set(self.voice_var.get())
            self.variation_var.set(config.config["voices"][voice].get("noise_scale", 0.667))
            self.speech_speed.set(config.config["voices"][voice].get("length_scale", 1.0))
            self.volume_var.set(config.config["voices"][voice].get("volume", 1.0))
            self.speaker_id.set(config.config["voices"][voice].get("speaker_id", 0))
        def save_changes(self):

            voice = self.name_var.get()
            vm.update_alias(
                name= voice,
                voice = self.voices[self.voice_name.current()],
                speaker = int(self.speaker_id.get() or 0),
                length_scale=float(self.speech_speed.get() or 1.0),
                noise_scale=float(self.variation_input.get() or 0.667)
            )
        def voice_id_callback(self, var, index, mode):
            voice = self.voice_var.get()
            if len(voice) == 0:
                return
            
            print("setting {} to {}".format(self.name_var.get(), voice))

            self.voice_config = vm.get_voice_config(voice) or {"num_speakers": 1}
            num_speaker = self.voice_config["num_speakers"]
            if self.speaker_id_var.get() > num_speaker - 1:
                self.speaker_id_var.set(0)

            vm.update_alias(self.name_var.get(), voice=voice)
            self.speaker_id.configure(to=num_speaker-1)
            self.voice_name.set(voice)

        # def speaker_id_callback(self, var, index, mode):
        #     vm.update_alias(self.name_var.get(), speaker=self.speaker_id_var.get())

        # def variation_callback(self, var, index, mode):
        #     vm.update_alias(self.name_var.get(), noise_scale=self.speaker_id_var.get())

        # def speed_callback(self, var, index, mode):
        #     vm.update_alias(self.name_var.get(), length_scale=self.speaker_id_var.get())

        def update_voices(self):
            self.voices=[]
            tmp = vm.get_all_installed_voices()
            for i, j in tmp:
                self.voices.append(i)
            self.voices.sort()
            
        def __init__(self, parent, *args, **kwargs):
            ttk.Frame.__init__(self, parent, *args, **kwargs)
            self.voice_config= dict()
            self.name_var = tk.StringVar()
            self.voice_var = tk.StringVar()
            self.voice_var.trace_add('write', self.voice_id_callback)

            # self.quality_var = tk.StringVar()
            self.speaker_id_var = tk.IntVar()
            #self.speaker_id_var.trace_add('write', self.speaker_id_callback)

            self.variation_var = tk.DoubleVar()
            #self.variation_var.trace_add('write', self.variation_callback)
                        
            self.speed_var = tk.DoubleVar()
            self.volume_var = tk.DoubleVar()
            self.pitch_var = tk.DoubleVar()
            self.voices = []

            self.update_voices()
            row = 0
            ttk.Label(self, text="Name").grid(row=row, column=0, padx=5, pady=5)
            self.name_entry = ttk.Label(self, textvariable=self.name_var)
            self.name_entry.grid(row=row, column=1, sticky=tk.NSEW, padx=5, pady=5)
            row += 1
            ttk.Label(self, text="Voice").grid(row=row, column=0, padx=5, pady=5)
            self.voice_name = ttk.Combobox(self, textvariable=self.voice_var, values=(self.voices), state=ttk.READONLY)
            
            self.voice_name.grid(row=row, column=1, padx=5, pady=5)
            row += 1
            ttk.Label(self, text="Speaker ID").grid(row=row, column=0, padx=5, pady=5)
            self.speaker_id = ttk.Spinbox(self, from_=0, to=0, increment=1, textvariable=self.speaker_id_var)
            self.speaker_id.grid(row=row, column=1, sticky=tk.NSEW, padx=5, pady=5) 
            row += 1
            ttk.Label(self, text="Variance").grid(row = row, column=0, padx=5, pady=5)
            self.variation_input = ttk.Spinbox(self, from_=0.0, to=2.0, increment=0.1, textvariable=self.variation_var)
            self.variation_input.grid(row=row, column=1, sticky=tk.NSEW, padx=5, pady=5)
            self.variation_input.bind("")
            row += 1

            ttk.Label(self, text="Speech speed").grid(row=row, column=0, padx=5, pady=5)
            self.speech_speed = ttk.Spinbox(self, from_=0.001, to=2.0, increment=0.1, textvariable=self.speed_var)
            self.speech_speed.grid(row=row, column=1, sticky=tk.NSEW, padx=5, pady=5)
            row += 1
            ttk.Label(self, text="Volume").grid(row=row, column=0, padx=5, pady=5)
            self.volume = ttk.Scale(self, from_=0.0, to=1.0, variable=self.volume_var)
            self.volume.grid(row=row, column=1, sticky=ttk.NSEW, padx=5, pady=5)
            row += 1
            self.save_button = ttk.Button(self, text="Save changes", command=self.save_changes)
            self.save_button.grid(row=row, column=0, columnspan=2, sticky=ttk.NSEW)



    def add_alias_callback(self):

        newname = Querybox.get_string(
            prompt="Enter the name of the alias",
            title="New voice alias",
            parent=self
        )

        if newname in config.config["voices"]:
            Messagebox.show_error(parent=self, message="Voice already exists.", title="Error")
            return
        
        vm.update_alias(newname)
        self.aliases.insert("", "end", iid=newname, text=newname)
        self.aliases.selection_set([newname])
        # self.frame.load_voice(newname)

    def select_voice_callback(self, event):
        for selection in self.aliases.selection():

            self.frame.load_voice(selection)
            break
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.aliases = ttk.Treeview(self, selectmode="browse")
        self.aliases.heading("#0", text="Aliases")


        for voice in config.config["voices"]:
            self.aliases.insert("", 'end', text=voice, iid=voice)
        
        self.aliases.grid(row=0, column=0, sticky=tk.NSEW)
        self.aliases.bind("<<TreeviewSelect>>", self.select_voice_callback)

        self.frame = VoiceAliasesTab.VoiceConfigFrame(self)

        self.add_button = ttk.Button(self, text="Add new alias", command=self.add_alias_callback)
        self.add_button.grid(row=1, column=0, sticky=ttk.NSEW)

        self.pack(expand=False, fill=tk.BOTH)
        

notebook.add(VoiceAliasesTab(notebook), text="Voice Aliases")

class DownloadVoicesTab(ttk.Frame):
    
    def set_installed(self, voice: str, installed: bool):
        """
        This may be called after the window is destroyed.
        """
        global window
        if window is None:
            return
    
        item = self.voices_list.item(voice)
        if isinstance(item["values"], list):
            item["values"][1] = "Yes" if installed else "No"
            self.voices_list.item(voice, values=item["values"])

    def handle_installbutton(self):
        selection = self.voices_list.selection()[0]

        item = self.voices_list.item(selection)
        if isinstance(item["values"], list):
            print(item)
            if vm.is_voice_installed(selection):
                used_aliases = []
                for voice in config.config["voices"]:
                    if config.config["voices"][voice].get("model_name", "") == voice:
                        used_aliases.append(voice)

                if len(used_aliases) != 0:
                    if len(used_aliases) == 1:
                        message = "alias"
                    else:
                        message = "aliases"
                    
                    Messagebox.show_error(message="This voice model is used by the following {}: {}".format(message, used_aliases.join(", ")))
                    return

                vm.uninstall_voice(selection)
                item["values"][1] = "No"
            else:
                item["values"][1] = "Downloading"
                # self.voices_list.item(selection, values=item["values"])
                vm.install_voice(selection, self.set_installed)
                # item["values"][1] = "Yes" if is_installed else "No"
            self.voices_list.item(selection, values=item["values"])

    def handle_addmanualbutton(self):
        
        paths = tkinter.filedialog.askopenfilename(parent=self, filetypes=[("ONNX voice model", "*.onnx")])
        print(paths)
        if len(paths) == 0:
            return 
        path = paths

        try:
            vm.register_voice(path)
            print("Registered voice {}".format(path))
        except Exception as e:
            import logging
            Messagebox.show_error(message="Could not open voice model. Make sure that the onnx.json file is in the same directory.")
            logging.error("Failed to find file", exc_info = e)

    """
    Download Voices tab

    Shows a Treeview with all the available voices to download
    """
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.voices_list = ttk.Treeview(self, selectmode="browse", columns=("C1", "C2", "C3", "C4"))
        self.voices_list.column("#0", stretch=tk.YES)
        self.voices_list.column("C1", width=70, stretch=tk.NO)
        self.voices_list.column("C2", width=70, stretch=tk.NO)
        self.voices_list.column("C3", width=70, stretch=tk.NO)
        self.voices_list.column("C4", width=80, stretch=tk.NO)
        self.voices_list.heading("#0", text="Name", anchor=tk.W)
        self.voices_list.heading("C1", text="Quality", anchor=tk.W)
        self.voices_list.heading("C2", text="Installed", anchor=tk.W)
        self.voices_list.heading("C3", text="Size", anchor=tk.W)
        self.voices_list.heading("C4", text="Speakers", anchor=tk.W)

        self.voices_list.grid(row=0, column=0, columnspan=5, padx=5, pady=5, sticky=tk.NSEW)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command = self.voices_list.yview)
        self.scrollbar.grid(row=0, column=6, sticky=tk.NS)
        self.voices_list.configure(yscrollcommand=self.scrollbar.set)
        self.parse_voices(vm.get_voices())
        self.installbutton=ttk.Button(self, text="Install/uninstall selected voice", command=self.handle_installbutton)
        self.installbutton.grid(row=1,column=0, columnspan=3)
        self.addmanualbutton= ttk.Button(self, text="Add voice from file", command = self.handle_addmanualbutton)
        self.addmanualbutton.grid(row=1,column=3, columnspan=3)
        self.pack(expand=False, fill="both")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

    # https://stackoverflow.com/a/14822210
    @staticmethod
    def convert_size(size_bytes):
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 1)
        return "%s %s" % (s, size_name[i])
    
    def parse_voices(self, voices: dict):
        # First pass: gather all the available languages
        categorized: dict[list] = dict()
        language_ids = set()
        for voice in voices:
            code = voices[voice]["language"]["code"]
            if not code in language_ids:
                categorized[code] = dict()

                # example: English (United States)
                friendly_name = "{} ({})".format(voices[voice]["language"]["name_english"], voices[voice]["language"]["country_english"])
                self.voices_list.insert("", "end", iid="/" + code, text=friendly_name)
                language_ids.add(code)
            is_installed = "Yes" if vm.is_voice_installed(voice) else "No"
            friendly_size = self.convert_size(vm.get_voice_size(voice))
            self.voices_list.insert("/" + code, "end", text=voices[voice]["name"], iid=voices[voice]["key"], 
                                    values=(
                                        voices[voice]["quality"],
                                        is_installed,
                                        friendly_size,
                                        voices[voice]["num_speakers"]))

download_voices_tab = DownloadVoicesTab(notebook)
notebook.add(download_voices_tab, text="Download Voices")

class SettingsTab(ttk.Frame):
    """
    Contains various settings for server ports, audio devices, etc. 
    """
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        
        row = 0
        ttk.Label(self, text="Server").grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="nesw")
        row += 1

        ttk.Checkbutton(self, text="WebSocket Server").grid(row=row, column=0, padx=5, pady=5)

        self.pack(fill="both")

settings_tab = SettingsTab(notebook)
notebook.add(settings_tab, text="Settings")


def poll():
    if config.running:
        window.after(500, poll)

signal.signal(signal.SIGINT, lambda x,y: do_close())

window.protocol("WM_DELETE_WINDOW", do_close)
window.after(500, poll)
window.mainloop()
do_close()
