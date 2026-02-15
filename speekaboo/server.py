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
import socketserver
from threading import Thread, Lock
import datetime
import logging
import json
import errno
from dataclasses import dataclass

from websockets import CloseCode
from websockets.sync.server import serve, ServerConnection


import config
import tts
import audio

# e.g. 2025-01-28T19:16:09.449827-05:00
def get_isoformat(time: datetime.datetime = datetime.datetime.now()):
    return time.astimezone().isoformat()

class SpeekabooHandler:
    """
    Base class for UDP and WebSocket handling
    """

    def cmd_speak(self, json_data: dict):
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

        if "message" not in json_data:
            raise ValueError("No message was provided")
        message = str(json_data["message"]).strip()

        if len(message) == 0:
            raise ValueError("Message is empty")
        if "voice" not in json_data:
            raise ValueError("No voice alias was provided")
        voice = str(json_data["voice"])

        if voice == "" or voice not in config.config["voices"]:
            raise ValueError("Voice alias not found")

        speech_id = tts.add(message, voice=voice)
        return {"speechId": speech_id, "text": message, "voiceName": voice, "pitch": 1.0, "volume": 1.0, "rate": 0.0}

    def cmd_stop(self, _json_data: dict):
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

    def cmd_enable(self, _json_data: dict):
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

    def cmd_disable(self, _json_data: dict):
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


    def cmd_pause(self, _json_data: dict | None = None):
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

    def cmd_resume(self, _json_data: dict | None = None):
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

    def cmd_clear(self, _json_data: dict):
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


    def cmd_getinfo(self, _json_data: dict):
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
            "speekabooVersion": "0.2.0"
        }

    
    # List of subscribable events, as reported by Speaker.bot 0.1.4
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
            "error"            # implemented
        ],
        "voicegate":[
            "profileactivated"
        ]
    }
    def cmd_getevents(self, _json_data: dict):
        """
        Undocumented.
        Returns a list of events that you can subscribe to.
        """
        return {
            "events": self.subscribable_events
        }

    def cmd_commands(self, _json_data: dict):
        """
        Returns a list of commands, required by Streamer.bot.
        """
        return { "commands": [*self.commands_websocket] }

    def cmd_getaliases(self, _json_data: dict):
        """
        Undocumented. 
        """
        voices = []
        for voice in config.config["voices"]:
            voices.append({"id": config.config["voices"][voice]["id"], "name": voice,  "voiceCount": 1})
        return { "aliases": voices }

    def cmd_nop(self, _json_data: dict):
        """
        A no-op
        """
        return {}

    def cmd_stub(self, json_data: dict):
        """
        A no-op that logs.
        """

        logging.warning("Calling stub function %s", json_data.get("request", json_data.get("command", "")))
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

    def log_server_error(self, err: OSError, protocol: str, addr: str, port: int):

        message = err.strerror
        match err.errno:
            case errno.EADDRINUSE:
                message = "Address in use. Is there another instance running?"
            case errno.EADDRNOTAVAIL:
                message = f"Address {protocol}://{addr}:{port} is unavailable. Check your firewall."
            case -2 | -3:
                message = f"Address {protocol}://{addr}:{port} is invalid."

        config.Event(
            "WebsocketEvent",
            "internal_event",
            "error",
            { "message": message }
        )


@dataclass
class ConnectionInfo:
    """
    Info for an active connection
    """
    websocket: ServerConnection
    subscribed_events: dict

class WSServer(Thread, SpeekabooHandler, config.Observer):
    """
    Websocket server thread handling Speaker.bot requests.
    """


    def do_subscribe(self, json_data: dict, conn_id: str):
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
        
        # sorry i'm lazy
        events = json.loads(json.dumps(json_data["events"]).lower())

        if not isinstance(events, dict):
            raise ValueError("Malformed json")

        subscribed = {}
        if conn_id in self.active_connections:
            subscribed = self.active_connections[conn_id].subscribed_events

        # If "*" is supplied, it subscribes to all events
        if "*" in events:
            subscribed = subscribed | self.subscribable_events
        
        else:
            for group in events:
                # Speaker.bot doesn't actually check this 
                # if not group in subscribable_events:
                #     raise ValueError("Unknown group name {}".format(group))

                if group in self.subscribable_events:
                    for event in events[group]:
                        if event == "*":
                            subscribed[group] |= self.subscribable_events[group]
                        else:
                            subscribed[group] |= events[group]


        # Add to the dictionary of subscriptions

        self.active_connections[conn_id].subscribed_events = subscribed

        logging.info("Subscribed %s, current events: %s", conn_id, subscribed)
        return {"events": events}

    def do_unsubscribe(self, json_data: dict, conn_id: str):
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

        if conn_id in self.active_connections:
            subscribed = self.active_connections[conn_id].subscribed_events
        if "*" in events:
            subscribed = {}

        else:
            for group in events:
                # Speaker.bot doesn't actually check this
                # if not group in subscribable_events:
                #     raise ValueError("Unknown group name {}".format(group))

                if group in self.subscribable_events:
                    for i in range(events[group]):
                        if events[group][i] == "*":
                            subscribed[group] =[]
                        elif events[group][i] in subscribed[group]:
                            for j in range(subscribed[group]):
                                if subscribed[group][j] == events[group][i]:
                                    del subscribed[group][j]
                                    break

        logging.debug("Unsubscribed %s, current events: %s", conn_id, subscribed)

        self.active_connections[conn_id].subscribed_events = subscribed
        return {"events":events}

    def handle_event(self, event_source: str, event_type: str, data: dict):
        """
        Handles a subscribable event, triggered by a config.Event
        
        Format:
        {
            "timeStamp": "iso timestamp in local time",
            "event": {"source": "source", "type": "event}
            "data": { ... }
        }
        """
        if event_source == "internal_event":
            return

        response = {}

        response["timeStamp"] = datetime.datetime.now().astimezone().isoformat()
        response["event"] = {
            "source": event_source,
            "type": event_type
        }
        response["data"] = data

        stringified = json.dumps(response)
        logging.info("Sending event %s", stringified)

        for conn_data in self.active_connections.values():
            if event_source.lower() not in conn_data.subscribed_events:
                continue
            if event_type not in conn_data.subscribed_events[event_source]:
                continue
            conn_data.websocket.send(stringified)


    def event_text_queued(self, _message: tts.MessageInfo):
        """
        todo
        """
        raise NotImplementedError()

    def parse_speaker_bot_websocket(self, message: str, conn_id: str) -> str:
        """
        Parses a websocket request.

        Returns the response as a string.
        """
        if len(message) > 10000:
            logging.error("Ignoring overly long message of %i bytes", len(message))
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
                response = self.do_subscribe(json_data, conn_id)
            elif request in ("UnSubscribe", "Unsubscribe"):
                response = self.do_unsubscribe(json_data, conn_id)
            else:
                response = self.commands_websocket.get(request, self.cmd_stub)(self,json_data)

            respjson = json.dumps({ "id": json_data["id"], "status": "ok", "result": response})

            logging.info("Responding %s", respjson)

            return respjson
        except ValueError as e:
            logging.error("Value Error in command: %s", request, exc_info=e)
            return json.dumps({"id": json_data["id"], "status": "error", "error": str(e) })


    def handle_websocket(self, websocket: ServerConnection):
        """
        Handler for a WebSocket connection.
        """

        if self.shutting_down:
            # Deny any new connections.
            websocket.close(CloseCode.GOING_AWAY)
            return

        # Create an ID for self.active_connections, e.g. 127.0.0.1:45748
        conn_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logging.info("New Websocket connection: %s", conn_id)

        # Add it to the active connection info.
        with self.lock:
            if conn_id in self.active_connections:
                logging.warning("Warning: Duplicate connection!!!")

            self.active_connections[conn_id] = ConnectionInfo(websocket, {})

        # Start parsing the messages until the WebSocket closes.
        for message in websocket:
            if not isinstance(message, str):
                logging.warning("Received bytes instead of str, trying to decode")
                try:
                    message = str(message, encoding="utf-8")
                except UnicodeDecodeError:
                    logging.error("Unicode decode error on bytes object")
                    websocket.send('{"error":"malformed command"}')
                    continue

            logging.info("Received WebSocket: %s", message)
            websocket.send(self.parse_speaker_bot_websocket(str(message), conn_id))

        # Delete the connection
        with self.lock:
            del self.active_connections[conn_id]


    def __init__(self, ws_addr: str = config.config["ws_server_addr"], ws_port: int = config.config["ws_server_port"]):
        """
        Constructor
        """
        Thread.__init__(self, name="Websocket Server Thread")
        config.Observer.__init__(self)
        self.observe('WebsocketEvent', self.handle_event)
        self.addr = ws_addr
        self.port = ws_port
        self.server = None
        self.lock = Lock()
        self.shutting_down = False

        self.active_connections: dict[str, ConnectionInfo] = {}


    def run(self):
        """
        Thread entry point for WSServer
        """
        if config.config["ws_server_enabled"]:
            try:
                with serve(self.handle_websocket, self.addr, self.port) as self.server:
                    logging.info("Running Websocket server at ws://%s:%d", self.addr, self.port)
                    config.Event(
                        "WebsocketEvent",
                        "internal_event",
                        "info",
                        { "message": f"Running WebSocket server at ws://{self.addr}:{self.port}."}
                    )
                    self.server.serve_forever()
            except OSError as err:
                logging.error("Error running Websocket server on ws://%s:%d: %s", self.addr, self.port, err)
                self.log_server_error(err, "ws", self.addr, self.port)

                self.server = None

    def stop(self):
        """
        Stops the WebSocket server.
        """
        if not self.is_alive():
            return
        logging.info("Shutting down WSServer...")
        if self.server is not None:
            self.shutting_down = True
            with self.lock:
                if len(self.active_connections) > 0:
                    logging.info("Waiting for connections to close...")
                    # Close all active connections
                    for conn in self.active_connections.values():
                        conn.websocket.close(CloseCode.GOING_AWAY)

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
        logging.error("Ignoring overly long message of %d bytes", len(message))
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
            self.data: bytes = self.request[0].strip()
            logging.info("Received UDP data: %s", self.data.decode("utf-8"))
            parse_speaker_bot_udp(udp_thread, self.data.decode("utf-8"))


    def __init__(self, udp_addr: str = config.config["udp_server_addr"], udp_port: int = config.config["udp_server_port"]):
        """
        Constructor
        """
        super().__init__(name="UDP Server Thread")
        self.addr = udp_addr
        self.port = udp_port
        self.server = None

    def run(self):
        """
        UDPServer thread entry point
        """
        if config.config["udp_server_enabled"]:
            try:
                with socketserver.UDPServer((self.addr, self.port), UDPServer.UDPHandler) as self.server: # type: ignore
                    logging.info("Running UDP server at udp://%s:%d", self.addr, self.port)
                    config.Event(
                        "WebsocketEvent",
                        "internal_event",
                        "info",
                        { "message": f"Running UDP server at udp://{self.addr}:{self.port}."}
                    )
                    self.server.serve_forever()

            except OSError as err:
                logging.error("Error running UDP server on udp://%s:%d: %s. Is there another instance running?", self.addr, self.port, err)
                self.log_server_error(err, "udp", self.addr, self.port)

                self.server = None

    def stop(self):
        """
        Shuts down the UDP server.
        """
        if not self.is_alive():
            return
        logging.info("Shutting down UDPServer...")
        if self.server is not None:
            self.server.shutdown()
            self.server = None
        self.join()

    def is_running(self) -> bool:
        return self.server is not None

# Global instances
udp_thread = UDPServer()
ws_thread = WSServer()
