from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
from watchdog.observers import Observer

import zmq
import zmq.asyncio
import os
import sys
import asyncio

try:
    from notify import notification
except:
    notification = lambda title, message, app_name: print(f"Result: {title}\n\t{message}")

class FileChecker(object):
    # Based on Hachiko's Event Handler
    def __init__(self, filename, sockets, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        if hasattr(asyncio, "create_task"):
            self._ensure_future = asyncio.create_task
        else:
            self._ensure_future = asyncio.ensure_future
        self._method_map = {
            "created": self.on_created, 
            "modified": self.on_modified
        }
        
        self.filename = filename
        self.sockets = sockets

    async def _send_if_is_watched_file(self, event):
        if os.path.basename(event.src_path) == self.filename:
            with open(event.src_path, 'r') as file:
                code = file.read()
                for socket in self.sockets:
                    try:
                        await socket.send_string(code)
                    except zmq.error.ZMQError as e:
                        # Ignore errors from ZMQ, possibly just an issue of sync
                        # between REQ and REP messages
                        pass


    async def on_modified(self, event):
        await self._send_if_is_watched_file(event)
    
    async def on_created(self, event):
        await self._send_if_is_watched_file(event)

    def dispatch(self, event):
        handler = self._method_map.get(event.event_type, None)
        if handler is not None:
            self._loop.call_soon_threadsafe(self._ensure_future, handler(event))

async def start_zmq_server(socket):
    while True:
        message = await socket.recv_string()
        if message and not message.startswith("PING"):
            reply = message
            title = "OK"
            if not reply.startswith("OK"):
                title = "FAIL"
            notification(title, message=reply, app_name='FFLiveCoding')

def zmq_create_sockets():
    context = zmq.asyncio.Context()
    cleansocket = context.socket(zmq.REP) 
    cleansocket.bind("tcp://*:5556")

    livesocket = context.socket(zmq.REP)
    livesocket.bind("tcp://*:5555")

    return cleansocket, livesocket


async def zmq_start_servers(sockets):
    await asyncio.gather(*[ start_zmq_server(socket) for socket in sockets])

async def osc_start_server():
    context = zmq.Context()
    oscbridgesocket = context.socket(zmq.PUB)
    oscbridgesocket.bind("tcp://*:5557")

    def clean_handler(address, *args):
        oscbridgesocket.send_string("/clean")

    def set_var_handler(address, *args):
        varname = args[0]
        value = args[1]
        oscbridgesocket.send_string(f"/set,{varname},{value}")

    dispatcher = Dispatcher()
    dispatcher.map("/clean",  clean_handler)
    dispatcher.map("/set", set_var_handler)
    server = osc_server.AsyncIOOSCUDPServer(("0.0.0.0", 5558), dispatcher, asyncio.get_event_loop())
    transport, protocol = await server.create_serve_endpoint()

def watchdog_start(directory_to_watch, checker):
    observer = Observer()
    observer.schedule(checker, path=directory_to_watch, recursive=False)
    observer.start()

def watchdog_prepare_file_checker(file, zmq_sockets):
    directory_to_watch = os.path.dirname(file)
    
    if not directory_to_watch:
        directory_to_watch = "./"

    return directory_to_watch, FileChecker(os.path.basename(file), zmq_sockets)

async def main(file):
    zmq_sockets = zmq_create_sockets()
    
    directory, checker = watchdog_prepare_file_checker(file, zmq_sockets)
    watchdog_start(directory, checker)
    
    osc_loop = osc_start_server()
    zmq_loop = zmq_start_servers(zmq_sockets)

    print(f"Watchdog is ready... you can now edit {file}")
    await asyncio.gather(
            osc_loop,
            zmq_loop
        )

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(sys.argv[0], description="Runs the watchdog to check for changes in a livecoding script")
    parser.add_argument("file", help="A JavaScript file to watch for changes.", type=str)
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.file))
    except KeyboardInterrupt:
        print("Closing... bye!")
