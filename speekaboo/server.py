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

from config import config, GLOBAL_UUID, messages
import socketserver
import websockets.sync.server as websockets
from threading import Thread
# from gui import messages
import uuid
import json

def cmd_speak(json_data: dict = {}):
    """
    Speak
       Speak the given message with the provided voice alias.
    Websockets:
    {
        "id": "<id>",
        "request": "Speak",
        "voice": "EventVoice"
        "message": "This is a test message",
        "badWordFilter": true
    }
    UDP:
    {
        "command": "speak",
        "id": "<id>",
        "voice": "<voice alias>",
        "message": "<message>"
    }
    """
    if enabled and len(json_data["message"].split()) < 25:
        messages.put(json_data["message"])
    return {}

def cmd_stop(json_data: dict = {}):
    """
    Stop
        If TTS is currently speaking, stop _only_ the current speech.
    
    Websockets:
    {
        "id": "<id>"
        "request": "Stop"
    }
    
    UDP:
    {
        "command": "stop"
    } 
    """
    global stop
    stop = True
    return {}

def cmd_enable(json_data: dict = {}):
    """
    Enable
        Enable the TTS engine

    Websockets:
    {
        "id": "<id>"
        "request": "Disable" (or "Off")
    }
    
    UDP:
    {
        "command": "disable" (or "off")
    }    
    """
    global enabled
    enabled = True
    return {}

def cmd_disable(json_data: dict = {}):
    """
    Disable
        Disable the TTS engine

    Websockets:
    {
        "id": "<id>"
        "request": "Disable" (or "Off")
    }
    
    UDP:
    {
        "command": "disable" (or "off")
    }    
    """
    global enabled
    enabled = False
    return {}


def cmd_pause(json_data: dict = {}):
    """
    Pause
    Pause the TTS event queue
    
    Websockets:
    {
        "id": "<id>"
        "request": "Pause"
    }
    
    UDP:
    {
        "command": "pause"
    }
    """
    global paused
    paused = True
    return {}

def cmd_resume(json_data: dict = {}):
    """
    Resume
    Resume the TTS event queue
    
    Websockets:
    {
        "id": "<id>"
        "request": "Resume"
    }
    
    UDP:
    {
        "command": "resume"
    }
    """
    global paused
    paused = False
    return {}

def cmd_clear(json_data: dict = {}):
    """
    Clear
    Clear all pending events in the TTS event queue
    
    Websockets:
    {
        "id": "<id>"
        "request": "Clear"
    }
    
    UDP:
    {
        "command": "clear"
    }
    """
    with messages.mutex:
        messages.queue.clear()
    return {}


def cmd_getinfo(json_data: dict = {}):
    """
    Returns version information, required by Streamer.bot.
    Just echo back what Speaker.bot 0.1.4 returns.
    """
    return {
        "instanceId": GLOBAL_UUID,
        "name": "Speaker.bot",
        "version": "0.1.4",
        "os": "windows",
        "apiVersion": 2
    }

def cmd_commands(json_data: dict = {}):
    """
    Returns a list of commands, required by Streamer.bot.
    """
    return { "commands": [*commands_websocket] }

def cmd_getaliases(json_data: dict = {}):
    """
    Undocumented. 
    """

def cmd_nop(json_data: dict = {}):
    """
    A no-op
    """
    return {}

def cmd_stub(json_data: dict = {}):
    """
    A no-op that logs.
    """
    print("Calling stub function {}".format(json_data.get("request", json_data.get("command", ""))))
    return {}

commands_websocket = {
    "Speak": cmd_speak,
    "Pause": cmd_pause,
    "Resume": cmd_resume,
    "Clear": cmd_clear,
    "Stop": cmd_stop,
    "Off": cmd_disable,
    "Disable": cmd_disable,
    "On": cmd_enable,
    "Enable": cmd_enable,
    "Events": cmd_stub,
    "Mode": cmd_stub,
    "GetEvent": cmd_stub,
    "Subscribe": cmd_nop,
    "Unsubscribe": cmd_nop,
    "GetInfo": cmd_getinfo,
    "GetAliases": cmd_stub,
    "GetState": cmd_stub,
    "GetVoiceGateProfiles": cmd_stub,
    "ActivateVoiceGateProfile": cmd_stub,
    "Commands": cmd_commands
}

commands_udp = {
    "speak": cmd_speak,
    "stop": cmd_stop,
    "enable": cmd_enable,
    "on": cmd_enable,
    "disable": cmd_disable,
    "off": cmd_disable,
    "profile": cmd_stub,
    "pause": cmd_pause,
    "resume": cmd_resume,
    "clear": cmd_clear,
    "events": cmd_stub,
    "reg": cmd_stub,
    "set": cmd_stub,
    "assign": cmd_stub
}

def parse_speaker_bot_websocket(message: str) -> dict:
    try:
        json_data = json.loads(message)
        response = {}
        request = json_data.get("request", "")
        response = commands_websocket.get(request, cmd_stub)(json_data)
        respjson = json.dumps({ "id": json_data["id"], "status": "ok", "result": response})
        print("Responding {}".format(respjson))
        return respjson
    except json.JSONDecodeError:
        print("Failed to parse Websocket message.")
        return {}

def parse_speaker_bot_udp(message: str):
    try:
        json_data: dict = json.loads(message)
        request = json_data.get("command", "")
        commands_udp.get(request, cmd_stub)(json_data)
    except json.JSONDecodeError:
        print("Failed to parse UDP packet.")

class WSServer(Thread):
    """
    Websocket server thread handling Speaker.bot requests.
    """
    @staticmethod
    def handle_websocket(websocket: websockets.ServerConnection):
        for message in websocket:
            print("Received Websocket: {}".format(message))
            websocket.send(parse_speaker_bot_websocket(message))


    def __init__(self, ws_addr: str = config["ws_server_addr"], ws_port: int = config["ws_server_port"]):
        super().__init__()
        self.addr = ws_addr
        self.port = ws_port
        self.server = None

    def run(self):
        if config["ws_server_enabled"]:
            try:
                with websockets.serve(WSServer.handle_websocket, self.addr, self.port) as self.server:
                    print("Running Websocket server at {}:{}".format(self.addr, self.port))
                    self.server.serve_forever()
            except OSError as err:
                print("Error running Websocket server on ws://{}:{}: {}".format(self.addr, self.port, err))
                print("Is there another instance running?")
                self.server = None

    def stop(self):
        print("Shutting down WSServer...")
        if self.server is not None:
            self.server.shutdown()
        self.join()

    def is_running(self) -> bool:
        return self.server is not None

class UDPServer(Thread):
    """
    UDP Server thread handling Speaker.bot requests.
    """
    class UDPHandler(socketserver.BaseRequestHandler):
        def setup(self):
            pass

        def handle(self):
            self.data = self.request[0].strip()
            print("Received UDP data: {}".format(self.data))

    def __init__(self, udp_addr: str = config["udp_server_addr"], udp_port: str = config["udp_server_port"]):
        super().__init__()
        self.addr = udp_addr
        self.port = udp_port
        self.server = None

    def run(self):
        if config["udp_server_enabled"]:
            try:
                with socketserver.UDPServer((self.addr, self.port), UDPServer.UDPHandler) as self.server:
                    print("Running UDP server at {}:{}".format(self.addr, self.port))
                    self.server.serve_forever()
            except OSError as err:
                print("Error running UDP server on udp://{}:{}: {}".format(self.addr, self.port, err))
                print("Is there another instance running?")
                self.server = None

    def stop(self):
        print("Shutting down UDPServer...")
        if self.server is not None:
            self.server.shutdown()
            self.server = None
        self.join()

    def is_running(self) -> bool:
        return self.server is not None