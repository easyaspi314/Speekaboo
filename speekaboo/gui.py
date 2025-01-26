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
import queue
from server import UDPServer, WSServer

def cmd_stop():
    print("STUB")

enabled = True
paused = False 
messages = queue.Queue()

udp_thread = UDPServer()
ws_thread = WSServer()

window = tk.Tk(className="Speekaboo")

window.title("Speekaboo")
sublabel = tk.Label(master=window, text="Listening on ws://localhost:7580 and udp://localhost:6990 for Speaker.bot commands. Look for PipeWire ALSA [python3.x] in App name.")
textbox = tk.Entry(master=window, width=100)

def manual_text():
    msg = textbox.get()
    textbox.delete(0, tk.END)
    if enabled:
        messages.put(msg)

def textbox_enter(event):
    manual_text()

textbox.bind("<Return>", textbox_enter)

def poll():
    window.after(500, poll)

def do_close():
    window.destroy()
    ws_thread.stop()
    udp_thread.stop()
    sys.exit(0)

enabledisabletext = tk.StringVar(value="Disable")
pauseresumetext = tk.StringVar(value="Pause")

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

buttonrow = tk.Frame(master=window)
playbutton = tk.Button(master=buttonrow, text="Play", width=20, command=manual_text)
stopbutton = tk.Button(master=buttonrow, text="Stop", width=20, command=cmd_stop)
enabledisablebutton = tk.Button(master=buttonrow, textvariable=enabledisabletext, width=20, command=toggle_enabled)
pauseresumebutton = tk.Button(master=buttonrow, textvariable=pauseresumetext, width=20, command=toggle_pause)
quitbutton = tk.Button(master=buttonrow, text="Quit", width=20, command=do_close)
sublabel.pack()
textbox.pack()
buttonrow.pack()

playbutton.pack(side=tk.LEFT)
stopbutton.pack(side=tk.LEFT)
enabledisablebutton.pack(side=tk.LEFT)
pauseresumebutton.pack(side=tk.LEFT)
quitbutton.pack(side=tk.LEFT)

signal.signal(signal.SIGINT, lambda x,y: do_close())

window.protocol("WM_DELETE_WINDOW", do_close)
window.after(500, poll)
window.mainloop()
do_close()
