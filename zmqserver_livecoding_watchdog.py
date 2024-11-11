from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
from watchdog.observers import Observer
from PyQt5.QtWidgets import (
        QWidget, QLabel, QVBoxLayout, QPushButton, QFileDialog, QStatusBar
        )
from qasync import QEventLoop, QApplication, asyncSlot, asyncClose

import zmq
import zmq.asyncio
import os
import sys
import asyncio
import puremagic

try:
    from notify import notification
except:
    notification = lambda title, message, app_name: print(f"Result: {title}\n\t{message}")

FFLIVE_CMD = "./bin/fflive -i pipe: -s scripts/livecoding.js"

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


class FFQtApp(QWidget):
    def __init__(self):
        super().__init__()
        self._ffgac = None
        self._fflive = None
        self._file = ""
        self._media_file = ""
        self._media_file_type = None
        self._webcam = False
        self._setupUI()
    
    def _setupUI(self):
        layout = QVBoxLayout()
        #self.label = QLabel("Choose a file to monitor")
        #layout.addWidget(self.label)

        self.statusbar = QStatusBar(self)
        self.statusbar.showMessage("Choose a file to start monitoring")
        layout.addWidget(self.statusbar)


        self.chooseFileButton = QPushButton("Choose File to Watch", self)
        self.chooseFileButton.clicked.connect(self.chooseFile)
        layout.addWidget(self.chooseFileButton)

        self.runBtserver = QPushButton("Run as RTMP server", self)
        self.runBtserver.clicked.connect(self.runRTMP)
        layout.addWidget(self.runBtserver)

        self.runBtloop = QPushButton("Run with video/image file", self)
        self.runBtloop.clicked.connect(self.runChooseFile)
        layout.addWidget(self.runBtloop)

        self.runBtwebcam = QPushButton("Run with webcam (Mac OS)", self)
        self.runBtwebcam.clicked.connect(self.runWebcam)
        layout.addWidget(self.runBtwebcam)



        self.restartFFBt = QPushButton("Restart ffglitch", self)
        self.restartFFBt.clicked.connect(self.restart_ffglitch)
        layout.addWidget(self.restartFFBt)
        
        # Set up window
        self.setLayout(layout)
        self.setWindowTitle('FFglitch livecoding')
        self.setGeometry(300, 300, 400, 300)
        
    @asyncSlot()
    async def runRTMP(self):
        self._media_file = ""
        self._webcam = False
        await self.run()

    @asyncSlot()
    async def runWebcam(self):
        self._media_file = ""
        self._webcam = True
        await self.run()

    @asyncSlot()
    async def runChooseFile(self):
        self._webcam = False
        file, _ = QFileDialog.getOpenFileName(self, "Choose a file", "", "All files (*)")
        if file:
            self._media_file = file
            self._media_file_type = None
            try:
                file_type = puremagic.magic_file(file)[0]
                if file_type.mime_type.startswith("image"):
                    self._media_file_type = "img"
                elif file_type.mime_type.startswith("video"):
                    self._media_file_type = "vid"
            except puremagic.PureError:
                pass

            if self._media_file_type is None:
                self.statusbar.showMessage("Failed to open file, is it image/video ?")
            else:
                await self.run()

    @asyncSlot()
    async def chooseFile(self):
        file, _ = QFileDialog.getOpenFileName(self, "Choose a file", "", "JavaScript Files (*.js)")
        if file:
            self.statusbar.showMessage(f"File chosen: {file}")
            self._file = file

    async def run_ffglitch(self):
        read, write = os.pipe()
        ffgac_cmd = "./bin/ffgac %s -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -fcode 5 -g max -sc_threshold max -mb_type_script scripts/mb_type_func_live_simple.js -f rawvideo pipe:"
        if self._media_file:
            if self._media_file_type == "vid":
                ffgac_cmd = ffgac_cmd % f"-stream_loop -1 -i {self._media_file}"
            elif self._media_file_type == "img":
                ffgac_cmd = ffgac_cmd % f"-loop 1 -i {self._media_file} -t 100000000" 
        elif self._webcam:
            ffgac_cmd = ffgac_cmd  % "-f avfoundation -r 30 -video_size 1280x720 -i default"
        else:
            ffgac_cmd = ffgac_cmd % "-listen 1 -i rtmp://127.0.0.1:5559/live"

        self._ffgac = await asyncio.create_subprocess_shell(
                ffgac_cmd,
                stdout=write,
                stderr=asyncio.subprocess.PIPE
                )
        os.close(write)
        self._fflive = await asyncio.create_subprocess_shell(
                FFLIVE_CMD,
                stdin=read,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
                )
        os.close(read)
        await asyncio.gather(
                 self._ffgac.communicate(),
                 self._fflive.communicate()
                 )

    @asyncSlot()
    async def run_task(self):
        await self.run_ffglitch()

    @asyncClose
    async def closeEvent(self, event):
        await self.stop_ffglitch()

    @asyncSlot()
    async def restart_ffglitch(self):
        await self.stop_ffglitch()
        await self.run_ffglitch()

    async def stop_ffglitch(self):
        if self._ffgac and self._fflive:
            try:
                self._ffgac.terminate()
            except ProcessLookupError:
                # For some reason ffgac has terminated already
                pass
            try:
                self._fflive.terminate()
            except ProcessLookupError:
                # For some reason fflive has terminated already
                pass
            await asyncio.gather(self._ffgac.wait(), self._fflive.wait())
            self._ffgac = None
            self._fflive = None

    async def run(self):
        file = self._file
        zmq_sockets = zmq_create_sockets()
    
        directory, checker = watchdog_prepare_file_checker(file, zmq_sockets)
        watchdog_start(directory, checker)
    
        osc_loop = osc_start_server()
        zmq_loop = zmq_start_servers(zmq_sockets)

        print(f"Watchdog is ready... you can now edit {file}")
        await asyncio.gather(
            osc_loop,
            zmq_loop,
            self.run_ffglitch()
            )


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

async def osc_start_server(app):
    context = zmq.Context()
    oscbridgesocket = context.socket(zmq.PUB)
    oscbridgesocket.bind("tcp://*:5557")

    def clean_handler(address, *args):
        oscbridgesocket.send_string("/clean")

    def set_var_handler(address, *args):
        varname = args[0]
        value = args[1]
        print(varname, value)
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


if __name__ == "__main__":
    #import argparse
    #parser = argparse.ArgumentParser(sys.argv[0], description="Runs the watchdog to check for changes in a livecoding script")
    #parser.add_argument("file", help="A JavaScript file to watch for changes.", type=str)
    #args = parser.parse_args()
    
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    window = FFQtApp()
    window.show()

    #loop.create_task(window.main())

    try:
        #asyncio.run(main(args.file))
        with loop:
            loop.run_until_complete(app_close_event.wait())
            loop.close()
    except KeyboardInterrupt:
        print("Closing... bye!")
        loop.close()
