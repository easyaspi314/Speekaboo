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
import re
import logging
import sys
import math
import signal
from typing import Any, Literal

import tkinter as tk
from tkinter import TclError, ttk, messagebox, simpledialog

import tkfilebrowser
import tktooltip
import darkdetect
import sv_ttk

import cuda_available
import onnxruntime as ort

import config
import event


from server import ws_thread, udp_thread
from voice_manager import vm
import audio
import tts

# Force encoding to UTF-8 to prevent crashes on Windows
sys.stdout.reconfigure(encoding="utf-8") # type: ignore
sys.stderr.reconfigure(encoding="utf-8") # type: ignore

class ExceptionHandlingTk(tk.Tk, event.Observer):
    """
    Tk root window, but with an active exception handler instead of just freezing.
    """
    def report_callback_exception(self, exc, val, tb):
        config.exception_hook(exc, val, tb, "Tkinter callback")

    def raise_error(self, message, info, *_args):
        messagebox.showerror(title="Error", message=message)
        do_close()

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        event.Observer.__init__(self)
        self.observe("raise_error", self.raise_error)


window = ExceptionHandlingTk(className="Speekaboo")
window.title("Speekaboo 0.2.0")

window.geometry("800x500")
window.minsize(width=800, height=500)

# Sun Valley theme
# Use darkdetect to match the system theme
sv_ttk.set_theme(darkdetect.theme() or "Light")

# Give the lists some padding.
style = ttk.Style()
style.configure("Treeview.Heading", padding=(10, 8))
old_height = style.configure("Treeview", "rowheight")
if isinstance(old_height, int):
    style.configure("Treeview", rowheight=old_height + 6)


notebook = ttk.Notebook(window, padding=5)
notebook.pack(expand=True, fill=tk.BOTH)

class LabeledWidget(ttk.Labelframe):
    """
    Wrapper for making widgets with labels
    """
    def __init__(self, parent, label_text: str, widget_type, *args, **kwargs):
        ttk.Labelframe.__init__(self, parent, padding=5, text=label_text, border=0)

        self.widget= widget_type(self, *args, **kwargs)
        self.widget.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        self.configure = self.widget.configure # type: ignore
        self.get = self.widget.get        # type: ignore
        self.set = self.widget.set        # type: ignore 

class ToolTip(tktooltip.ToolTip):
    """
    Just a helper so I don't have to type the delay
    """
    def __init__(self, parent, text, *args, delay=1, **kwargs):
        super().__init__(parent, *args, msg=text, delay=delay, **kwargs)

def do_close():
    """
    Shut down the program
    """
    global window # pylint:disable=global-statement

    if not config.running:
        return
    config.running = False

    if window is not None:
        window.destroy()
        window = None

    vm.wait_for_downloads()
    audio.audio.stop()
    ws_thread.stop()
    udp_thread.stop()
    tts.tts_thread.stop()
    config.save_config()

    sys.exit(0)


class MainTab(ttk.Frame, event.Observer):
    """
    Main tab
    
    Contains:
       - Main controls
       - Log
       - Manual textbox
    """
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        event.Observer.__init__(self)
        self.observe("WebsocketEvent", self.handle_event)
        self.observe("aliases_list_updated", self.update_alias)
        row = 0

        scrollable_wrapper = ttk.Panedwindow(self, orient=tk.VERTICAL)
        scrollable_wrapper.grid(row=row, column=0, columnspan=5, sticky=tk.NSEW)        

        log_frame = ttk.Frame(scrollable_wrapper)

        self.log_box = ttk.Treeview(log_frame, selectmode="browse")
        self.log_box.heading("#0", text="Log", anchor=tk.W)


        log_v_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_box.yview)
        log_v_scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        self.log_box.pack(expand=True, fill=tk.BOTH)

        self.log_box.configure(yscrollcommand=log_v_scrollbar.set)

        scrollable_wrapper.add(log_frame, weight=1)

        queue_frame= ttk.Frame(scrollable_wrapper)


        self.queue_box = ttk.Treeview(queue_frame, selectmode="browse")
        self.queue_box.heading("#0", text="Queue", anchor=tk.W)

        queue_v_scrollbar = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_box.yview)
        queue_v_scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        self.queue_box.pack(expand=True, fill=tk.BOTH)

        self.queue_box.configure(yscrollcommand=queue_v_scrollbar.set)

        scrollable_wrapper.add(queue_frame, weight=1)

        self.grid_rowconfigure(row, weight=1)

        row += 1

        # Skip the temp voice, which has the key of empty string.
        self.alias_select = ttk.Combobox(self, width=1)
        self.update_alias()
        self.alias_select.grid(row=row, column=0, sticky=tk.NSEW, padx=5, pady=5)

        self.manual_text = ttk.Entry(self)
        self.manual_text.grid(row=row, column=1, columnspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.manual_text.bind("<Return>", self.manual_send)

        self.play_button = ttk.Button(self, text="Speak", command=self.manual_send)
        self.play_button.grid(row=row, column=4, sticky=tk.NSEW, padx=5, pady=5)

        row += 1

        self.stop_button = ttk.Button(self, text="Stop", command=audio.audio.stop_playback)
        self.stop_button.grid(row=row, column=0, padx=5, pady=5, sticky=tk.NSEW)
        ToolTip(self.stop_button, text="Stop the currently playing message")
        self.pause_button_var = tk.StringVar(value="Pause")
        pause_button = ttk.Button(self, textvariable=self.pause_button_var, command=self.pause)
        pause_button.grid(row=row, column=1, padx=5, pady=5, sticky=tk.NSEW)
        ToolTip(pause_button, text="Pause/resume the queue.")
        
        self.disable_button_var= tk.StringVar(value="Disable")
        disable_button = ttk.Button(self, textvariable=self.disable_button_var, command=self.disable)
        disable_button.grid(row=row, column=2, padx=5, pady=5, sticky=tk.NSEW)
        ToolTip(disable_button, text="Enable/Disable queueing and playback")
        self.quit_button = ttk.Button(self, text="Clear",  command=self.clear)
        self.quit_button.grid(row=row, column=3, padx=5, pady=5, sticky=tk.NSEW)
        ToolTip(self.quit_button, text="Clears the queue")
        self.quit_button = ttk.Button(self, text="Quit", command=do_close)
        self.quit_button.grid(row=row, column=4, columnspan=2, padx=5, pady=5, sticky=tk.NSEW)
        ToolTip(self.quit_button, text="Quits the program")

        for i in range(5):
            self.grid_columnconfigure(i, weight=1, uniform="main_buttons")

        self.pack(expand=True, fill="both")

    def pause(self):
        self.pause_button_var.set("Pause" if config.paused else "Resume")

        config.paused = not config.paused

    def disable(self):
        self.disable_button_var.set("Enable" if config.enabled else "Disable")

        config.enabled = not config.enabled

    def clear(self):
        queued = tts.to_list()
        tts.clear()
        for message in queued:
            self.queue_box.delete(message.id)

    def manual_send(self, _event=None):
        """
        Event trigger for a manual TTS request
        """
        if len(config.config["voices"]) == 0:
            messagebox.showerror(parent=window, message="Before you can use the TTS, add a voice in the Manage Voices tab and then create a Voice Alias!")
            return

        msg = self.manual_text.get()
        voice = self.alias_select.get()
        if len(voice) == 0:
            messagebox.showerror(parent=window, message="Please select a voice")
            return
        self.manual_text.delete(0, tk.END)

        tts.add(msg, voice)

    def update_alias(self, *_args):

        aliases = [voice for voice in config.config["voices"] if voice != '']
        flag = len(self.alias_select["values"]) == 0 and len(aliases) > 0
        selected = self.alias_select.get()
        # removed the selected voice!
        if len(aliases) > 0 and selected not in config.config["voices"]:
            flag = True

        self.alias_select["values"] = aliases
        if flag:
            self.alias_select.set(aliases[0])

    def write_to_log(self, message: str):
        self.log_box.insert("", tk.END, text=message)
        # Scroll to the bottom
        self.log_box.yview_moveto(1.0)

    def write_to_queue(self, message: dict):
        self.queue_box.insert('', 0, iid=message["id"], text=message["text"])

        self.queue_box.yview_moveto(0.0)

    def handle_event(self, event_source: str, event_type: str = '', data: dict|None = None):
        # print(event_source, event_type, data)
        if window is None or data is None:
            logging.info("Event on dead instance")
            return

        if event_source == "internal_event":
            match event_type:
                case "loading_voice":
                    self.write_to_log(f"Loading voice: {data['voice']}")
                case "loaded_voice":
                    self.write_to_log(f"Loaded voice {data['voice']}, Estimated memory usage: {data['mem']:.1f} MiB")
                case "warn":
                    self.write_to_log(f"EWarning: {data['message']}")
                case "info":
                    self.write_to_log(f"Info: {data['message']}")
        else:
            match event_type:
                case "textqueued":
                    self.write_to_log(f"Queued: {data['text']}")
                    self.write_to_queue(data)
                case "engineprocessed":
                    self.write_to_log(f"Processed: {data['text']}")
                case "playing":
                    self.write_to_log(f"Playing: {data['text']}")
                    if self.queue_box.exists(data["id"]):
                        self.queue_box.delete(data["id"])
                case "error":
                    self.write_to_log(f"Error: {data['text']}: {data.get('speekaboo_exception', 'Unknown')}")
                    if self.queue_box.exists(data["id"]):
                        self.queue_box.delete(data["id"])



main_tab = MainTab(window)
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
    class VoiceConfigFrame(ttk.Frame, event.Observer):
        """
        Frame for voice options
        """
        def __init__(self, parent, *args, **kwargs):
            ttk.Frame.__init__(self, parent, *args, **kwargs)
            event.Observer.__init__(self)
            self.observe("voices_changed", self.update_voices)

            self.voice_config= {}
            self.name_var = tk.StringVar()
            self.voice_var = tk.StringVar()
            self.voice_var.trace_add('write', self.voice_id_callback)

            self.speaker_id_var = tk.IntVar()
            self.variation_var = tk.DoubleVar()
            self.speed_var = tk.DoubleVar()
            self.volume_var = tk.DoubleVar()
            # self.pitch_var = tk.DoubleVar()
            self.length_variation_var = tk.DoubleVar()
            self.voices = []

            row = 0
            ttk.Label(self, text="Name").grid(row=row, column=0, padx=5, pady=5)
            name_entry = ttk.Label(self, textvariable=self.name_var)
            name_entry.grid(row=row, column=1, sticky=tk.NSEW, padx=5, pady=5)
            row += 1
            self.voice_widget = LabeledWidget(self, "Voice", ttk.Combobox, textvariable=self.voice_var, values=())
            self.update_voices()
            self.voice_widget.grid(row=row, column=0, padx=5, pady=5, sticky=tk.NSEW)
            ToolTip(self.voice_widget, text="Selects which voice file (.onnx) to use")

            self.speaker_id = LabeledWidget(self, "Speaker ID", ttk.Spinbox, from_=0, to=0, increment=1, textvariable=self.speaker_id_var)
            self.speaker_id.grid(row=row, column=1, padx=5, pady=5, sticky=tk.NSEW)
            ToolTip(self.speaker_id, text="Some voices contain multiple speakers.")

            row += 1

            variation_input = LabeledWidget(self, "Pitch Variance", ttk.Spinbox, from_=0.0, to=2.0, increment=0.1, textvariable=self.variation_var)
            variation_input.grid(row=row, column=0, padx=5, pady=5, sticky=tk.NSEW)
            ToolTip(variation_input, text="How much variance to put in the voice pitch. Piper arg: noise_scale")

            volume = LabeledWidget(self, "Volume", ttk.Scale, from_=0.0, to=1.0, variable=self.volume_var)
            volume.grid(row=row, column=1, padx=5, pady=5, sticky=tk.NSEW)

            row += 1

            speech_speed = LabeledWidget(self, "Speech speed", ttk.Spinbox, from_=0.001, to=2.0, increment=0.1, textvariable=self.speed_var)
            speech_speed.grid(row=row, column=0, padx=5, pady=5, sticky=tk.NSEW)
            ToolTip(speech_speed, text="Shorter is faster. Controls the length of each phoneme. Piper arg: length_scale")

            noise_w = LabeledWidget(self, "Speech speed variance", ttk.Spinbox, from_=0.001, to=2.0, increment=0.1, textvariable=self.length_variation_var)
            noise_w.grid(row=row, column=1, padx=5, pady=5, sticky=tk.NSEW)
            ToolTip(noise_w, text="How much variance to put into the length of each phoneme. Piper arg: noise_w")

            row += 1
            save_button = ttk.Button(self, text="Save changes", command=self.save_changes)
            save_button.grid(row=row, column=0, padx=5, pady=5, sticky=tk.NSEW)

            test_button = ttk.Button(self, text="Test", command=self.test_voice)
            test_button.grid(row=row, column=1, padx=5, pady=5, sticky=tk.NSEW)

            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)

        def load_voice(self, voice: str):
            """
            Loads a voice and populates the variables
            """
            self.tkraise()
            self.name_var.set(voice)
            self.voice_var.set(config.config["voices"][voice].get("model_name", ''))
            self.voice_widget.widget.set(self.voice_var.get())
            self.variation_var.set(config.config["voices"][voice].get("noise_scale", 0.667))
            self.length_variation_var.set(config.config["voices"][voice].get("noise_w", 0.8))
            self.speed_var.set(config.config["voices"][voice].get("length_scale", 1.0))
            self.volume_var.set(config.config["voices"][voice].get("volume", 1.0))
            self.speaker_id.set(config.config["voices"][voice].get("speaker_id", 0))

        def save_voice(self, voice: str):
            """
            Saves the voice
            """
            if self.voice_widget.widget.current() == -1:
                if len(self.voices) == 0:

                    messagebox.showerror(parent=window, message="Please select a voice. Voices can be downloaded in the Manage Voices tab.")
                else:
                    messagebox.showerror(parent=window, message="Please select a voice first.")

                return

            vm.update_alias(
                name= voice,
                voice = self.voices[self.voice_widget.widget.current()],
                speaker = int(self.speaker_id.get() or 0),
                length_scale=self.speed_var.get(),
                noise_scale=self.variation_var.get(),
                noise_w=self.length_variation_var.get(),
                volume=self.volume_var.get()
            )
            logging.info("Saving voice '%s': %s", voice, config.config["voices"][voice])

        def test_voice(self):
            """
            Saves the voice to empty string temp voice
            """
            self.save_voice("")
            tts.add(message="This is a test message", voice="")

        def save_changes(self):
            voice = self.name_var.get()
            self.save_voice(voice)

        def voice_id_callback(self, _var, _index, _mode):
            """
            Triggered when voice_var is changed
            """
            voice = self.voice_var.get()
            if len(voice) == 0:
                return
            
            logging.info("setting %s to %s", self.name_var.get(), voice)

            self.voice_config = vm.get_voice_config(voice) or {"num_speakers": 1}
            num_speaker = self.voice_config["num_speakers"]
            if self.speaker_id_var.get() > num_speaker - 1:
                self.speaker_id_var.set(0)

            vm.update_alias(self.name_var.get(), voice=voice)
            self.speaker_id.widget.configure(to=num_speaker-1)
            self.voice_widget.widget.set(voice)

        def update_voices(self, _voice = "", _installed = False):
            """
            Update the voices list
            """
            self.voices=[]
            tmp = vm.get_all_installed_voices()
            for i, _j in tmp:
                self.voices.append(i)
            self.voices.sort()
            self.voice_widget.widget["values"] = self.voices
            
    def add_alias_callback(self):
        """
        Callback for when the Add alias button is pressed
        """

        # TODO: theming
        newname = simpledialog.askstring(
            prompt="Enter the name of the alias",
            title="New voice alias",
            parent=window
        )

        if newname is None: # user pressed cancel
            return

        newname = newname.strip()

        if newname in config.config["voices"]:
            messagebox.showerror(parent=window, message="Voice already exists.")
            return

        if len(newname) == 0:
            messagebox.showerror(parent=window, message="The name cannot be blank.")
            return

        vm.update_alias(newname)
        self.aliases.insert("", tk.END, iid=newname, text=newname)
        self.aliases.selection_set([newname])

        event.Event("aliases_list_updated")

    def remove_alias_callback(self):
        """
        Removes an alias.
        """
        if len(self.aliases.selection()) != 1:
            messagebox.showerror(parent=window, message="Select a voice first!")
            return
        alias = self.aliases.selection()[0]
        result = messagebox.askyesno(
            parent=window,
            title="Remove alias?",
            message=f"Remove {alias}? This cannot be undone and may cause queued voices to fail."
        )

        if not result:
            return

        del config.config["voices"][alias]

        self.aliases.delete(alias)
        event.Event("aliases_list_updated")
        self.placeholder.tkraise()

    def rename_alias_callback(self):
        if len(self.aliases.selection()) != 1:
            messagebox.showerror(parent=window, message="Select a voice first!")
            return
        alias = self.aliases.selection()[0]

        if alias not in config.config["voices"]:
            messagebox.showerror(parent=window, message="Whoops, can't find that alias. This is a bug!")
            return
        
        result = simpledialog.askstring(
            parent=window,
            title="Rename alias",
            prompt="Enter the new name for this alias. This may cause existing messages to fail.",
            initialvalue=alias
        )

        if result is None:
            return
        result = result.strip()

        if result in config.config["voices"]:
            messagebox.showerror(message="This voice alias already exists.")
            return

        if len(result) == 0:
            messagebox.showerror(message="The name cannot be blank.")
            return

        config.config["voices"][result] = config.config["voices"][alias]
        del config.config["voices"][alias]

        idx = self.aliases.index(alias)

        self.aliases.delete(alias)
        
        self.aliases.insert("", idx, iid=result, text=result)
        self.frame.load_voice(result)
        event.Event("aliases_list_updated")
        
    def select_voice_callback(self, _event):
        for selection in self.aliases.selection():
            self.frame.load_voice(selection)
            break

        

    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)

        self.pack(expand=True, fill=tk.BOTH)

        aliases_frame = ttk.Frame(self)
        self.aliases = ttk.Treeview(aliases_frame, selectmode="browse")
        self.aliases.heading("#0", text="Aliases", anchor=tk.W)

        for voice in config.config["voices"]:
            # Skip the temp voice, which is empty string
            if voice == "":
                continue
            self.aliases.insert("", tk.END, text=voice, iid=voice)

        scrollbar = ttk.Scrollbar(aliases_frame, orient=tk.VERTICAL, command=self.aliases.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.aliases.pack(expand=True, fill=tk.BOTH)

        self.aliases.bind("<<TreeviewSelect>>", self.select_voice_callback)

        self.aliases.configure(yscrollcommand=scrollbar.set)
        aliases_frame.grid(row=0, column=0, padx=5, pady=5)

        self.placeholder = ttk.Label(self, text="Select or create an alias to edit.", anchor=tk.CENTER)
        self.placeholder.configure(justify="center")
        self.placeholder.grid(row=0, column=1, columnspan=2,  sticky=tk.NSEW)
        self.frame = VoiceAliasesTab.VoiceConfigFrame(self)
        self.frame.grid(row=0, column=1, columnspan=2, sticky=tk.NSEW)

        self.placeholder.tkraise()

        self.add_button = ttk.Button(self, text="Add new alias", command=self.add_alias_callback)
        self.add_button.grid(row=1, column=0, padx=5, pady=5, sticky=tk.NSEW)

        self.remove_button = ttk.Button(self, text="Remove selected alias", command=self.remove_alias_callback)
        self.remove_button.grid(row=1, column=1, padx=5, pady=5, sticky=tk.NSEW)

        self.rename_button = ttk.Button(self, text="Rename selected alias", command=self.rename_alias_callback)
        self.rename_button.grid(row=1, column=2, padx=5, pady=5, sticky=tk.NSEW)

        for i in range(3):
            self.grid_columnconfigure(i, weight=1, uniform="voice_aliases")
        self.grid_rowconfigure(0, weight=1)



notebook.add(VoiceAliasesTab(window), text="Voice Aliases")

class DownloadVoicesTab(ttk.Frame, event.Observer):
    """
    Download Voices tab

    Shows a Treeview with all the available voices to download
    """ 
    def set_installed(self, voice: str, installed: bool):
        """
        Observer callback. This may be called after the window is destroyed.
        """

        if window is None:
            return
        # not in list and installing? add it to additional voices
        if not self.voices_list.exists(voice) and installed:
            self.voices_list.insert("/additional_voices", tk.END, iid=voice, text=voice)
            return

        
        item = self.voices_list.item(voice)
        parent = self.voices_list.parent(voice)
        if parent == '/additional_voices' and not installed:
            self.voices_list.delete(voice)
        elif parent != '' and isinstance(item["values"], list):
            item["values"][1] = "Yes" if installed else "No"

            self.voices_list.item(voice, values=item["values"])

    def check_for_alias(self, name: str):
        """
        Checks if a voice is used in an alias, and displays an error if it does
        """
        used_aliases = vm.get_used_aliases(name)
        if len(used_aliases) != 0:
            if len(used_aliases) == 1:
                message = "alias"
            else:
                message = "aliases"

            messagebox.showerror(
                parent=window,
                message=f"This voice model is used by the following {message}: {', '.join(used_aliases)}. Remove the aliases or change the linked voice model first."
            )
            return True

        return False

    def handle_installbutton(self):
        """
        Handles the install button
        """
        if len(self.voices_list.selection()) == 0:
            return

        selection = self.voices_list.selection()[0]
        item = self.voices_list.item(selection)

        # Manually installed voice
        if self.voices_list.parent(selection) == '/additional_voices':
            if self.check_for_alias(selection):
                return
            vm.deregister_voice(selection)
        elif self.voices_list.parent(selection) != '':
            if vm.is_voice_installed(selection):
                if self.check_for_alias(selection):
                    return

                vm.uninstall_voice(selection)
            elif isinstance(item["values"], list):
                item["values"][1] = "Downloading"
                vm.install_voice(selection)

                self.voices_list.item(selection, values=item["values"])

    def handle_addmanualbutton(self):
        """
        Handler for adding manual voices
        """

        real_treeview_insert = ttk.Treeview.insert

        def treeview_insert_patch(self: ttk.Treeview, parent: str, index: int | Literal['end'], iid: str|int|None =None, **kwargs):
            """
            UGLY HACK:
                TkFileBrowser has a bug where if you bookmark a mounted drive on Linux, it will crash
                because it tries to add the same bookmark twice.

                I might fork the old file browser, bugs aside it is so much nicer than native Tk.
            """
            if iid is not None and self.exists(iid):
                return str(iid)

            return real_treeview_insert(self, parent, index, iid, **kwargs)
        # patch treeview
        ttk.Treeview.insert = treeview_insert_patch
        # ask for file
        path = tkfilebrowser.askopenfilename(parent=self, filetypes=[("ONNX voice model (*.onnx)", "*.onnx")])
        # unpatch treeview
        ttk.Treeview.insert = real_treeview_insert

        if len(path) == 0: # user pressed cancel
            return

        try:
            vm.register_voice(str(path))
            logging.info("Registered voice %s", path)

        except ValueError as e:
            messagebox.showerror(
                parent=window,
                message="Could not open voice model. Make sure when installing VOICE.onnx, VOICE.onnx.json is in the same directory."
            )
            logging.error("Failed to find file", exc_info=e)


    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        event.Observer.__init__(self)

        self.observe("voices_changed", self.set_installed)
        treeview_container = ttk.Frame(self)
        treeview_container.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)
        treeview_container.grid_columnconfigure(0, weight=1)
        treeview_container.grid_rowconfigure(0, weight=1)
        self.voices_list = ttk.Treeview(treeview_container, selectmode="browse", columns=("C1", "C2", "C3", "C4"))
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

        self.voices_list.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(treeview_container, orient=tk.VERTICAL, command=self.voices_list.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.voices_list.configure(yscrollcommand=scrollbar.set)

        self.parse_voices()
        self.installbutton=ttk.Button(self, text="Install/uninstall selected voice", command=self.handle_installbutton)
        self.installbutton.grid(row=1,column=0, padx=5, pady=5, sticky=tk.NSEW)
        self.addmanualbutton= ttk.Button(self, text="Add voice manually from file", command = self.handle_addmanualbutton)
        self.addmanualbutton.grid(row=1, column=1, padx=5, pady=5, sticky=tk.NSEW)
        self.pack(expand=True, fill="y")
        for i in range(2):
            self.grid_columnconfigure(i, weight=1, uniform='install_button')
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
    
    def parse_voices(self):
        # Clear the voices
        if len(self.voices_list.get_children()) > 0:
            self.voices_list.delete(*self.voices_list.get_children())


        manual_voices = config.config["additional_voices"]

        self.voices_list.insert("", 0, iid="/additional_voices", text="Manually installed voices")
        if len(manual_voices) != 0:
            for key in manual_voices:
                self.voices_list.insert("/additional_voices", tk.END, iid=key, text=key)


        downloadable_voices = vm.get_downloadable_voices()

        # First pass: gather all the available languages
        categorized: dict[str, dict] = {}
        language_ids = set()
        for voice, value in downloadable_voices.items():
            code = value["language"]["code"]
            if not code in language_ids:
                categorized[code] = {}

                # example: English (United States)
                friendly_name = f"{value['language']['name_english']} ({value['language']['country_english']})"
                self.voices_list.insert("", "end", iid="/" + code, text=friendly_name)
                language_ids.add(code)
            is_installed = "Yes" if vm.is_voice_installed(voice) else "No"
            friendly_size = self.convert_size(vm.get_voice_size(voice))
            if not self.voices_list.exists(value["key"]):
                self.voices_list.insert("/" + code, "end", text=value["name"], iid=value["key"],
                                        values=(
                                            value["quality"],
                                            is_installed,
                                            friendly_size,
                                            value["num_speakers"]))

download_voices_tab = DownloadVoicesTab(window)
notebook.add(download_voices_tab, text="Manage Voices")

class ConfigVar(tk.Variable):
    """
    Wrapper for Tk variables to make them automatically write to config.config
    """
    def write_to_config(self, _var, _index, _mode):
        val: str | int | float = 0
        try:
            val = self.get()
        except TclError:
            return

        if isinstance(config.config[self.key_name], bool):
            val = bool(val)

        config.config[self.key_name] = val

    def __init__(self, parent, key_name, *args, default_value = None,  **kwargs):
        super().__init__(parent, config.config[key_name] or default_value, *args, **kwargs)
        self.key_name = key_name

        self.trace_add("write", self.write_to_config)


class ConfigStringVar(ConfigVar, tk.StringVar):
    """ String version of the ConfigVar """

class ConfigIntVar(ConfigVar, tk.IntVar):
    """ Int version of the ConfigVar """

class ConfigDoubleVar(ConfigVar, tk.DoubleVar):
    """ Float version of the ConfigVar """


class SettingsTab(ttk.Frame):
    """
    Contains various settings for server ports, audio devices, etc. 
    """
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs, padding=5)

        vcmd = (self.register(self.validate_ip_addr), '%P')
        ivcmd = (self.register(self.on_invalid),)

        row = 0
        ttk.Label(self, text="Most changes require a restart.").grid(row=row, column=0, columnspan=4, padx=5, pady=5, sticky=tk.W)
        row += 1
        ttk.Label(self, text="Server").grid(row=row, column=0, columnspan=4, padx=5, pady=5, sticky=tk.W)
        row += 1

        ws_check = ttk.Checkbutton(self, text="WebSocket Server", variable=ConfigIntVar(self, "ws_server_enabled"))
        ws_check.grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        udp_check = ttk.Checkbutton(self, text="UDP Server", variable=ConfigIntVar(self, "udp_server_enabled"))
        udp_check.grid(row=row, column=2, columnspan=2, padx=5, pady=5, sticky=tk.W)
        row += 1
        self.ws_addr_var = ConfigStringVar(self, key_name="ws_server_addr")
        ws_addr = ttk.Entry(self, name="ws", textvariable=self.ws_addr_var,
                            validate='focusout', validatecommand=vcmd, invalidcommand=ivcmd)
        ws_addr.grid(row=row, column=0, padx=5, pady=5, sticky=tk.EW)
        ToolTip(ws_addr, text="IPv4 address for the WebSocket server (default 127.0.0.1)")

        ws_port = ttk.Spinbox(self, from_=0, to=65535, textvariable=ConfigIntVar(self, key_name="ws_server_port"))
        ws_port.grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        ToolTip(ws_port, text="Port for the WebSocket server (default 7580)")

        self.udp_addr_var = ConfigStringVar(self, key_name="udp_server_addr")
        udp_addr = ttk.Entry(self, name="udp", textvariable=self.udp_addr_var,
                            validate='focusout', validatecommand=vcmd, invalidcommand=ivcmd)

        ToolTip(udp_addr, text="IPv4 address for the UDP server (default 0.0.0.0)")
        udp_addr.grid(row=row, column=2, padx=5, pady=5, sticky=tk.EW)
        udp_port = ttk.Spinbox(self, from_=0, to=65535, textvariable=ConfigIntVar(self, key_name="udp_server_port"))
        udp_port.grid(row=row, column=3, padx=5, pady=5, sticky=tk.EW)
        ToolTip(udp_port, text="Port for the WebSocket server (default 6669)")
        row += 1

        ttk.Label(self, text="Voices").grid(row=row, column=0, columnspan=4, padx=5, pady=5, sticky=tk.W)
        row += 1
        mem_limit = LabeledWidget(self, "Voice cache (MiB)", ttk.Spinbox, from_=128, to=config.system_mem // 4, textvariable=ConfigIntVar(self, key_name="max_memory_usage"))
        mem_limit.grid(row=row, column=0, padx=5, pady=5, sticky=tk.EW)

        ToolTip(mem_limit, text="Each voice takes approximately 100 MB in memory, and they take a while to load,"
                                "so Speekaboo will cache the most recently used voices in memory. Note that"
                                "changing the speaker ID is free.")

        onnx_mem_limit = LabeledWidget(self, "ONNX Memory Limit (MiB)", ttk.Spinbox, from_=128, to=config.system_mem // 4, textvariable=ConfigIntVar(self, key_name="onnx_memory_limit"))
        onnx_mem_limit.grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)

        ToolTip(onnx_mem_limit, text="Limits the max memory usage that ONNX can use. 1 GiB is usually a safe option.")

        num_threads = LabeledWidget(self, "CPU Threads (0=auto)", ttk.Spinbox, from_=0, to=config.cpu_count, textvariable=ConfigIntVar(self, key_name="num_threads"))
        num_threads.grid(row=row, column=2, padx=5, pady=5, sticky=tk.EW)

        ToolTip(num_threads, text="How many CPU threads to use when generating TTS. In practice, there is very little benefit past 6 threads.")

        word_limit = LabeledWidget(self, "Word limit (0=off)", ttk.Spinbox, from_=0, to=999, textvariable=ConfigIntVar(self, key_name="max_words"))
        word_limit.grid(row=row, column=3, sticky=tk.EW)

        ToolTip(word_limit, "Prevents playing messages if there are too many words. Set to 0 to disable this limit. Make sure you set an ONNX memory limit.")


        # TODO: CUDA. Memory limit for GPU is complicated and there is very little performance
        # benefit for short bursts

        # cuda_enabled_state = tk.DISABLED
        # if cuda_available.getCudaDeviceCount() == 0:
        #     cuda_tooltip = "Currently only supported on NVIDIA GPUs"
        #     config.config["use_cuda"] = False
        # elif "CUDAExecutionProvider" not in ort.get_available_providers():
        #     cuda_tooltip = "Your GPU seems to be supported, but you need to install the CUDA variant of ONNX:\n    python -m pip install onnxruntime-gpu"
        #     config.config["use_cuda"] = False
        # else:
        #     cuda_enabled_state = tk.NORMAL
        #     cuda_tooltip = "Uses your GPU to process TTS. May be beneficial if you don't have many CPU cores."


        # cudabox = ttk.Checkbutton(self, text="Use CUDA acceleration", state=cuda_enabled_state, variable=ConfigIntVar(self, key_name="use_cuda"))
        # cudabox.grid(row=row, column=2, columnspan=2, padx=5, pady=5, sticky=tk.W)
        # ToolTip(cudabox, text=cuda_tooltip)
        row += 1

        # not implemented yet
        self.devices_list = ["[Default]"] + list(audio.audio.get_devices())
        self.device_var = tk.StringVar()
        if config.config["output_device"] is None:
            self.device_var.set("[Default]")
        elif config.config["output_device"] not in self.devices_list:
            self.device_var.set(f"(not found) {config.config['output_device']}")
        else:
            self.device_var.set(config.config["output_device"])

        self.device_var.trace_add("write", self.set_audio_device)
        self.device_select = LabeledWidget(self, "Output device", ttk.Combobox, values=self.devices_list, textvariable=self.device_var, state="readonly")

        self.device_select.grid(row=row, column=0, columnspan=4, padx=5, pady=5, sticky=tk.NSEW)



        for i in range(4):
            self.grid_columnconfigure(i, weight=1, uniform="config")

        self.pack(fill=tk.BOTH, expand=False)

    def set_audio_device(self, _index, _value, _op):
        device = self.device_var.get()
        if device == "[Default]" and self.device_select.widget.current() == 0:
            config.config["output_device"] = None
        else:
            config.config["output_device"] = device
    

    def validate_ip_addr(self, value: str):
        """
        Validates an IPv4 address.

        Adapted from https://www.pythontutorial.net/tkinter/tkinter-validation/
        """
        pattern = r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'
        if re.fullmatch(pattern, value) is None:
            return False
        numbers = value.split('.')
        for num in numbers:
            if int(num) > 255:
                return False

        return True

    def on_invalid(self):
        """
        Show an error message if the data is not valid

        TODO: try to change it back
        """

        messagebox.showerror(parent=window, message="Please enter a valid IPv4 address.")

settings_tab = SettingsTab(window)
notebook.add(settings_tab, text="Settings")

def poll():
    """
    Polling loop to keep the Tk thread happy and to listen for exceptions
    """
    if len(config.waiting_exceptions) > 0:
        # whoops, we have an exception, show it to the user and exit
        for name, exc in config.waiting_exceptions.items():
            messagebox.showerror(
                title="Exception!",
                message=f"Fatal exception in {name}:\n{exc[0].__name__}(\"{exc[1]}\")"
            )
        do_close()
        return

    if config.running and window is not None:
        window.after(100, poll)

# Catch KeyboardInterrupt gracefully
signal.signal(signal.SIGINT, lambda _x, _y: do_close())

# Run cleanup when the user closes the window
window.protocol("WM_DELETE_WINDOW", do_close)

# Run a slow polling loop to make sure that the main thread can process things
window.after(100, poll)

def start_threads():
    # Start worker threads
    audio.audio.initialize()
    ws_thread.start()
    udp_thread.start()
    audio.audio.start()
    tts.tts_thread.start()

window.after(80, start_threads)

window.mainloop()
# unreachable
do_close()
