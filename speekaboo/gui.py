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

import sys
import signal
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
import queue
from server import UDPServer, WSServer
import config
import voice_manager
import uuid
import math
import audio
import threading
import message_queue
def cmd_stop():
    print("STUB")

udp_thread = UDPServer()
udp_thread.start()
ws_thread = WSServer()
ws_thread.start()

audio_thread =threading.Thread(target=audio.start_thread)
audio_thread.start()
window = ttk.Window()
window.geometry("600x400")
window.title("Speekaboo")

notebook = ttk.Notebook(window)
notebook.pack(expand=True, fill="both", padx=5, pady=5)

vm = voice_manager.VoiceManager()

def do_close():
    config.running = False
    global window
    if window is not None:
        window.destroy()
        window = None
    print("Waiting for downloads")
    vm.wait_for_downloads()
    print("Waiting for audio thread")
    audio_thread.join()
    ws_thread.stop()
    udp_thread.stop()
    config.save_config()
    sys.exit(0)

class MainTab(ttk.Frame):
    def manual_send(self, event=None):
        msg = self.manual_text.get()
        self.manual_text.delete(0, tk.END)

        message_queue.add(msg)

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

        self.manual_text = ttk.Entry(self, text="hello")
        self.manual_text.grid(row=row, column=0, columnspan=4, sticky="nesw", padx=5, pady=5)
        self.manual_text.bind("<Return>", self.manual_send)
        self.play_button = ttk.Button(self, text="Speak", command=self.manual_send)
        self.play_button.grid(row=row, column=4, sticky="nesw", padx=5, pady=5)
        row += 1

        self.stop_button = ttk.Button(self, text="Stop", bootstyle="secondary")
        self.stop_button.grid(row=row, column=0, sticky="nesw", padx=5, pady=5)
        ToolTip(self.stop_button, text="Stop the currently playing message")
        self.pause_button = ttk.Button(self, text="Pause", bootstyle="secondary")
        self.pause_button.grid(row=row, column=1, sticky="nesw", padx=5, pady=5)
        ToolTip(self.pause_button, text="Pause/resume the queue.")
        self.disable_button = ttk.Button(self, text="Disable", bootstyle="secondary")
        self.disable_button.grid(row=row, column=2, sticky="nesw", padx=5, pady=5)
        ToolTip(self.disable_button, text="Enable/Disable queueing and playback")
        self.quit_button = ttk.Button(self, text="Clear", bootstyle="secondary", command=do_close)
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
    pass

class DownloadVoicesTab(ttk.Frame):
    
    def set_installed(self, voice: str, installed: bool):
        """
        This may be called after the window is destroyed.
        """
        global window
        if window is None:
            return
    
        item = self.voices_list.item(voice)
        print(item)
        if isinstance(item["values"], list):
            item["values"][1] = "Yes" if installed else "No"
            self.voices_list.item(voice, values=item["values"])

    def handle_installbutton(self):
        selection = self.voices_list.selection()[0]

        item = self.voices_list.item(selection)
        if isinstance(item["values"], list):
            print(item)
            if vm.is_voice_installed(selection):
                vm.uninstall_voice(selection)
                item["values"][1] = "No"
            else:
                item["values"][1] = "..."
                # self.voices_list.item(selection, values=item["values"])
                vm.install_voice(selection, self.set_installed)
                # item["values"][1] = "Yes" if is_installed else "No"
            self.voices_list.item(selection, values=item["values"])
        
        
        

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
        self.installbutton.grid(row=1,column=0, columnspan=6)
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
    window.after(500, poll)

"""

sublabel = ttk.Label(window, text="Listening on ws://localhost:7580 and udp://localhost:6990 for Speaker.bot commands. Look for PipeWire ALSA [python3.x] in App name.")
sublabel.grid(row=0, column=0, sticky="ew")

textbox = ttk.Entry(window)
textbox.grid(row=1, column=0, sticky="ew")

window.grid_columnconfigure(0, weight=1)

def manual_text():
    msg = textbox.get()
    textbox.delete(0, tkinter.END)
    if enabled:
        messages.put(msg)

def textbox_enter(event):
    manual_text()

textbox.bind("<Return>", textbox_enter)

enabledisabletext = tkinter.StringVar(value="Disable")
pauseresumetext = tkinter.StringVar(value="Pause")

def toggle_enabled():
    if enabled:
        enabledisabletext.set("Enable")
    else:
        enabledisabletext.set("Disable")
    enabled = not enabled 

def toggle_pause():
    if paused:
        pauseresumetext.set("Pause")
    else:
        pauseresumetext.set("Resume")
    paused = not paused

buttonrow = ttk.Frame(master=window)
buttonrow.grid(row=2, column=0)
playbutton = ttk.Button(master=buttonrow, text="Play", command=manual_text)
stopbutton = ttk.Button(master=buttonrow, text="Stop", command=cmd_stop)
enabledisablebutton = ttk.Button(master=buttonrow, textvariable=enabledisabletext, command=toggle_enabled)
pauseresumebutton = ttk.Button(master=buttonrow, textvariable=pauseresumetext, command=toggle_pause)
quitbutton = ttk.Button(master=buttonrow, text="Quit", command=do_close)

playbutton.grid(row=0, column=0)
stopbutton.grid(row=0, column=1)
enabledisablebutton.grid(row=0, column=2)
pauseresumebutton.grid(row=0, column=3)
quitbutton.grid(row=0, column=4)

for i in range(5):
    buttonrow.grid_columnconfigure(i, weight=1)
# sublabel.pack()
# textbox.pack()
# buttonrow.pack()

# playbutton.pack(side=tkinter.LEFT)
# stopbutton.pack(side=tkinter.LEFT)
# enabledisablebutton.pack(side=tkinter.LEFT)
# pauseresumebutton.pack(side=tkinter.LEFT)
# quitbutton.pack(side=tkinter.LEFT)
"""
signal.signal(signal.SIGINT, lambda x,y: do_close())

window.protocol("WM_DELETE_WINDOW", do_close)
window.after(500, poll)
window.mainloop()
do_close()
