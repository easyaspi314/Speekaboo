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
import socketserver
import websockets.sync.server as websockets
from threading import Thread
from gui import messages
import uuid
import json

g_uuid = str(uuid.uuid4())
def cmd_speak(json_data={}):
    if enabled and len(json_data["message"].split()) < 25:
        messages.put(json_data["message"])
    return {}

def cmd_pause(json_data={}):
    global paused
    paused = True
    return {}

def cmd_resume(json_data={}):
    global paused
    paused = False
    return {}

def cmd_clear(json_data={}):
    with messages.mutex:
        messages.queue.clear()
    return {}

def cmd_stop(json_data={}):
    global stop
    stop = True
    return {}

def cmd_stub(json_data={}):
    print("Calling stub function {}".format(json_data.get("request", json_data.get("command", ""))))
    return {}

def cmd_getinfo(json_data={}):
    return {
        "instanceId": g_uuid,
        "name": "Speaker.bot",
        "version": "0.1.4",
        "os": "windows",
        "apiVersion": 2
    }


def cmd_disable(json_data={}):
    global enabled
    enabled = False
    return {}

def cmd_enable(json_data={}):
    global enabled
    enabled = True
    return {}

def cmd_commands(json_data={}):
    return { "commands": [*commands_websocket] }

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
    "Subscribe": cmd_stub,
    "Unsubscribe": cmd_stub,
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

def parse_speaker_bot_websocket(message: str):
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
        json_data = json.loads(message)
        request = json_data.get("command", "")
        response = commands_udp.get(request, cmd_stub)(json_data)
    except json.JSONDecodeError:
        print("Failed to parse UDP packet.")

class WSServer(Thread):
    """
    Websocket server thread handling Speaker.bot requests.
    """
    @staticmethod
    def handle_websocket(websocket):
        for message in websocket:
            print("Received Websocket: {}".format(message))
            parse_speaker_bot_websocket(message)

    def __init__(self, ws_addr = "127.0.0.1", ws_port = 7580):
        super().__init__()
        self.addr = ws_addr
        self.port = ws_port

    def run(self):
        with websockets.serve(WSServer.handle_websocket, self.addr, self.port) as self.server:
            print("Running Websocket server at {}:{}".format(self.addr, self.port))
        
            self.server.serve_forever()

    def stop(self):
        print("Shutting down WSServer...")
        self.server.shutdown()
        self.join()


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

    def __init__(self, udp_addr = "0.0.0.0", udp_port = 6669):
        super().__init__()
        self.addr = udp_addr
        self.port = udp_port
        self.server = None

    def run(self):
        with socketserver.UDPServer((self.addr, self.port), UDPServer.UDPHandler) as self.server:
            print("Running UDP server at {}:{}".format(self.addr, self.port))
            self.server.serve_forever()

    def stop(self):
        print("Shutting down UDPServer...")
        self.server.shutdown()
        self.join()
