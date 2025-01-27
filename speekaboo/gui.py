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
import tkinter
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
import queue
from server import UDPServer, WSServer
import config
from piper import PiperVoice 
from piper.download import get_voices

def cmd_stop():
    print("STUB")

enabled = True
paused = False 
messages = queue.Queue()

udp_thread = UDPServer()
udp_thread.start()
ws_thread = WSServer()
ws_thread.start()

window = ttk.Window()
window.geometry("600x400")
window.title("Speekaboo")

notebook = ttk.Notebook(window)
notebook.pack(expand=True, fill="both", padx=5, pady=5)

def do_close():
    window.destroy()
    ws_thread.stop()
    udp_thread.stop()
    config.save_config()
    sys.exit(0)

class MainTab(ttk.Frame):
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
        self.play_button = ttk.Button(self, text="Speak")
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

voicedata = None

def load_voices():
    global voicedata



# class CreateVoiceDialog(ttk.Toplevel):
#     def __init__(self, *args, **kwargs):
#         ttk.Frame.__init__(self, *args, **kwargs)
#         if voicedata is None and config.data_folder is not None:
#             voicedata = get_voices(config.data_folder, False)
            

#         pass

class VoicesTab(ttk.Frame):

    """
    Voices tab

    Contains:
       - List of installed voice aliases
       - Default voice selection
       - Button to create or edit a voice alias
    """
    pass



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
