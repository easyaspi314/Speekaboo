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
from threading import Thread, Lock
import json
import tts
import audio
import datetime
import logging

# e.g. 2025-01-28T19:16:09.449827-05:00
def get_isoformat(time: datetime.datetime = datetime.datetime.now()):
    return time.astimezone().isoformat()

class SpeekabooHandler:

    def send_event(self, event_source, event_type, data):
        print("Calling stub!")
        pass

    def cmd_speak(self, json_data: dict = {}):
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
        if not "message" in json_data:
            raise ValueError("No message was provided")
        message = str(json_data["message"]).strip()

        if len(message) == 0:
            raise ValueError("Message is empty")
        if not "voice" in json_data:
            raise ValueError("No voice alias was provided")
        voice = str(json_data["voice"])
        if not voice in config.config["voices"]:
            raise ValueError("Voice alias not found")
        
        id = tts.add(message, voice=voice)
        return {"speechId": id, "text": message, "voiceName": voice, "pitch": 1.0, "volume": 1.0, "rate": 0.0}

    def cmd_stop(self, json_data: dict = {}):
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
        audio.audio.stop_playback()

        return {}

    def cmd_enable(self, json_data: dict = {}):
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
        config.enabled = True
        return {}

    def cmd_disable(self, json_data: dict = {}):
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
        config.enabled = False
        return {}


    def cmd_pause(self, json_data: dict = {}):
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
        config.paused = True
        return {}

    def cmd_resume(self, json_data: dict = {}):
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
        config.paused = False
        return {}

    def cmd_clear(self, json_data: dict = {}):
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
        tts.clear()
        return {}


    def cmd_getinfo(self, json_data: dict = {}):
        """
        Returns version information, required by Streamer.bot.
        Just echo back what Speaker.bot 0.1.4 returns, with a hint
        that this is actually Speekaboo.
        """
        
        return {
            "instanceId": config.GLOBAL_UUID,
            "name": "Speaker.bot",
            "version": "0.1.4",
            "os": "windows",
            "apiVersion": 2,
            "speekabooVersion": "0.1.0"
        }

    """
    List of subscribable events, as reported by Speaker.bot 0.1.4
    """
    subscribable_events = {
        "application":[
            "startedspeaking", # not implemented
            "stoppedspeaking"  # not implemented
        ],
        "texttospeech":[
            "textqueued",      # implemented
            "engineprocessed", # implemented
            "playing",         # implemented
            "finished",        # implemented
            "deleted",         # not implemented
            "error"            # not implemented
        ],
        "voicegate":[
            "profileactivated"
        ]
    }
    def cmd_getevents(self, json_data: dict= {}):
        """
        Undocumented.
        Returns a list of events that you can subscribe to.
        """
        return {
            "events": self.subscribable_events
        }

    def cmd_commands(self, json_data: dict = {}):
        """
        Returns a list of commands, required by Streamer.bot.
        """
        return { "commands": [*self.commands_websocket] }

    def cmd_getaliases(self, json_data: dict = {}):
        """
        Undocumented. 
        """
        voices = []
        for voice in config.config["voices"]:
            voices.append({"id": config.config["voices"][voice]["id"], "name": voice,  "voiceCount": 1})
        return { "aliases": voices }

    def cmd_nop(self, json_data: dict = {}):
        """
        A no-op
        """
        return {}

    def cmd_stub(self, json_data: dict = {}):
        """
        A no-op that logs.
        """
        logging.warning("Calling stub function {}".format(json_data.get("request", json_data.get("command", ""))))
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
        "GetEvents": cmd_stub,
        "Subscribe": cmd_nop,   # handled specially
        "Unsubscribe": cmd_nop, # handled specially
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



class WSServer(Thread, SpeekabooHandler):
    """
    Websocket server thread handling Speaker.bot requests.
    """

    def do_subscribe(self, json_data: dict, id: str):
        """
        Subscribe
        Subscribes to a list of events (Websockets only)

        Uses the same format as Streamer.bot requests

        Websockets:
        {
            "id": "<id>",
            "request": "Subscribe",
            "events": {
                "groupName|*": [
                    "event1",
                    "event2",
                    "..."
                ]
            }
        }
        """
        if "events" not in json_data:
            raise ValueError("No events provided")
        
        events = json.loads(json.dumps(json_data["events"]).lower())
        if not isinstance(events, dict):
            raise ValueError("Malformed json")
        subscribed = {}
        if id in self.active_connections:
            subscribed = self.active_connections[id]["events"]

        # If "*" is supplied, it subscribes to all events
        if "*" in events:
            subscribed = subscribed | self.subscribable_events
        
        else:
            for group in events:
                """
                # Speaker.bot doesn't actually check this 
                if not group in subscribable_events:
                    raise ValueError("Unknown group name {}".format(group))
                """
                if group in self.subscribable_events:
                    for event in events[group]:
                        if event == "*":
                            subscribed[group] |= self.subscribable_events[group]
                        else:
                            subscribed[group] |= events[group]

        """
        Add to the dictionary of subscriptions
        """
        self.active_connections[id]["events"] = subscribed

        logging.info("Subscribed {}, current events: {}".format(id, subscribed))
        return {"events": events}               

    def do_unsubscribe(self, json_data: dict, id: str):
        """
        UnSubscribe / Unsubscribe
        Unsubscribes from a list of events (Websockets only)

        Uses the same format as Streamer.bot requests

        Websockets:
        {
            "id": "<id>",
            "request": "UnSubscribe", // or Unsubscribe
            "events": {
                "type|*": [
                    "event1",
                    "event2",
                    "..."
                ],
                ...
            }
        }
        """
        if "events" not in json_data:
            raise ValueError("No events provided")
        
        events = json_data["events"]
        if not isinstance(events, dict):
            raise ValueError("Malformed json")
        subscribed = {}
        if id in self.active_connections:
            subscribed = self.active_connections[id]["events"]

        if "*" in events:
            subscribed = {}
        
        else:
            for group in events:
                """
                # Speaker.bot doesn't actually check this 
                if not group in subscribable_events:
                    raise ValueError("Unknown group name {}".format(group))
                """
                if group in self.subscribable_events:
                    for i in range(events[group]):
                        if events[group][i] == "*":
                            subscribed[group] =[]
                        elif events[group][i] in subscribed[group]:
                            for j in range(subscribed[group]):
                                if subscribed[group][j] == events[group][i]:
                                    del subscribed[group][j]
                                    break

        logging.debug("Unsubscribed {}, current events: {}".format(id, subscribed))

        self.active_connections[id]["events"] = subscribed
        return {"events":events}
    
    def send_event(self, event_source, event_type, data):
        """
        Sends a subscribed event to all listeners.
        
        Format:
        {
            "timeStamp": "iso timestamp in local time",
            "event": {"source": "source", "type": "event}
            "data": { ... }
        }
        """

        response = dict()

        response["timeStamp"] = datetime.datetime.now().astimezone().isoformat()
        response["event"] = {
            "source": event_source,
            "type": event_type
        }
        response["data"] = data

        stringified = json.dumps(response)
        logging.info("Sending event {}".format(stringified))
        for id in self.active_connections:
            if not "events" in self.active_connections[id]:
                continue
            if not event_source.lower() in self.active_connections[id]["events"]:
                continue
            if not event_type in self.active_connections[id]["events"][event_source]:
                continue
            self.active_connections[id]["websocket"].send(stringified)
        pass

    def event_text_queued(self, message: tts.MessageInfo):
        """
        todo
        """
        pass

    def parse_speaker_bot_websocket(self, message: str, id: str) -> str:
        """
        Parses a websocket request.

        Returns the response as a string.
        """
        if len(message) > 10000:
            logging.error("Ignoring overly long message of {} bytes".format(len(message)))
            return '{"error":"message too long"}'

        try:
            json_data = json.loads(message)
        except json.JSONDecodeError:
            logging.error("Failed to parse Websocket message.")
            return '{"error":"malformed command"}'

        if "request" not in json_data or "id" not in json_data:
            logging.error("Missing id or request in command")
            return '{"error":"malformed command"}'

        if not isinstance(json_data["request"], str) or not isinstance(json_data["id"], str):
            logging.error("Invalid json type for request/id")
            return '{"error":"malformed json"}'
        
        response = {}
        request = json_data["request"]
        try:
            if request == "Subscribe":
                response = self.do_subscribe(json_data, id)
            elif request == "UnSubscribe" or request == "Unsubscribe":
                response = self.do_unsubscribe(json_data, id)
            else:
                response = self.commands_websocket.get(request, self.cmd_stub)(self,json_data)
        
            respjson = json.dumps({ "id": json_data["id"], "status": "ok", "result": response})

            logging.info("Responding {}".format(respjson))

            return respjson
        except ValueError as e:
            logging.error("Value Error in command: {}".format(e))
            return json.dumps({"id": json_data["id"], "status": "error", "error": str(e) })


    def handle_websocket(self, websocket: websockets.ServerConnection):
        """
        Handler for a WebSocket connection.
        """

        if self.shutting_down:
            # Deny any new connections.
            websocket.close(websockets.CloseCode.GOING_AWAY)
            return

        # Create an ID for self.active_connections, e.g. 127.0.0.1:45748
        id = "{}:{}".format(*websocket.remote_address)
        logging.info("New Websocket connection: {}".format(id))

        # Add it to the active connection info.
        with self.lock:
            if id in self.active_connections:
                logging.warning("Warning: Duplicate connection!!!")
            
            self.active_connections[id] = {"websocket": websocket, "events": {}}

        # Start parsing the messages until the WebSocket closes.
        for message in websocket:
            logging.info("Received WebSocket: {}".format(message))
            websocket.send(self.parse_speaker_bot_websocket(message, id))

        # Delete the connection
        with self.lock:
            del self.active_connections[id]


    def __init__(self, ws_addr: str = config.config["ws_server_addr"], ws_port: int = config.config["ws_server_port"]):
        """
        Constructor
        """
        super().__init__()
        self.addr = ws_addr
        self.port = ws_port
        self.server = None
        self.lock = Lock()
        self.shutting_down = False
        self.active_connections: dict[str, dict] =  dict()


    def run(self):
        """
        Thread entry point for WSServer
        """
        if config.config["ws_server_enabled"]:
            try:
                with websockets.serve(self.handle_websocket, self.addr, self.port) as self.server:
                    logging.info("Running Websocket server at {}:{}".format(self.addr, self.port))
                    self.server.serve_forever()
            except OSError as err:
                logging.error("Error running Websocket server on ws://{}:{}: {}. Is there another instance running?".format(self.addr, self.port, err))
                self.server = None

    def stop(self):
        """
        Stops the WebSocket server.
        """
        logging.info("Shutting down WSServer...")
        if self.server is not None:
            self.shutting_down = True
            with self.lock:
                if len(self.active_connections) > 0:
                    logging.info("Waiting for connections to close...")
                    # Close all active connections
                    for conn in self.active_connections:
                        self.active_connections[conn]["websocket"].close(websockets.CloseCode.GOING_AWAY)

                self.active_connections.clear()

            self.server.shutdown()

            self.shutting_down = False
            self.server = None
        self.join()

    def is_running(self) -> bool:
        return self.server is not None

def parse_speaker_bot_udp(thread, message: str):
    """
    Parses a UDP request. 
    """
    if len(message) > 10000:
        logging.error("Ignoring overly long message of {} bytes".format(len(message)))
        return

    json_data: dict = json.loads(message)
    request = json_data.get("command", "")
    SpeekabooHandler.commands_udp.get(request, SpeekabooHandler.cmd_stub)(thread, json_data)

udp_thread = None

class UDPServer(Thread, SpeekabooHandler):

    """
    UDP Server thread handling Speaker.bot requests.
    """
    class UDPHandler(socketserver.BaseRequestHandler):
        """
        socketserver request handler class
        """
        def setup(self):
            pass

        def handle(self):
            """
            Handles a UDP connection.
            """
            self.data = self.request[0].strip()
            logging.info("Received UDP data: {}".format(self.data))
            parse_speaker_bot_udp(udp_thread, self.data.decode("utf-8"))


    def __init__(self, udp_addr: str = config.config["udp_server_addr"], udp_port: str = config.config["udp_server_port"]):
        """
        Constructor
        """
        super().__init__()
        self.addr = udp_addr
        self.port = udp_port
        self.server = None

    def run(self):
        """
        UDPServer thread entry point
        """
        if config.config["udp_server_enabled"]:
            try:
                with socketserver.UDPServer((self.addr, self.port), UDPServer.UDPHandler) as self.server:
                    logging.info("Running UDP server at {}:{}".format(self.addr, self.port))
                    self.server.serve_forever()

            except OSError as err:
                logging.error("Error running UDP server on udp://{}:{}: {}. Is there another instance running?".format(self.addr, self.port, err))
                self.server = None

    def stop(self):
        """
        Shuts down the UDP server.
        """
        logging.info("Shutting down UDPServer...")
        if self.server is not None:
            self.server.shutdown()
            self.server = None
        self.join()

    def is_running(self) -> bool:
        return self.server is not None

"""
Global instances
"""
udp_thread = UDPServer()
udp_thread.start()
ws_thread = WSServer()
ws_thread.start()