from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
from watchdog.observers import Observer
from PyQt5.QtWidgets import (
        QWidget, QLabel, QVBoxLayout, QPushButton, QFileDialog, QStatusBar,
        QMessageBox
        )
from PyQt5.QtCore import QObject, pyqtSignal
from qasync import QEventLoop, QApplication, asyncSlot, asyncClose

import asyncio
import logging
import os
import platform
import sys
import puremagic
import zmq
import zmq.asyncio

try:
    from notify import notification
except:
    notification = lambda title, message, app_name: wdlogger.info(f"Result: {title}\n\t{message}")

#logging.basicConfig(level=logging.NOTSET)
applogger = logging.getLogger(__name__)
applogger.setLevel(logging.DEBUG)
applogger.setLevel(logging.DEBUG)
_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.DEBUG)
_stream_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
applogger.addHandler(_stream_handler)
zmqlogger = applogger.getChild("ZMQ")
osclogger = applogger.getChild("OSC")
wdlogger = applogger.getChild("watchdog")
fflogger = applogger.getChild("ffglitch")
 
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return relative_path

FFLIVE_CMD = f"\"{get_resource_path('./bin/fflive')}\" -hide_banner -loglevel error -i pipe: -s \"{get_resource_path('scripts/livecoding.js')}\""

class FileChecker(object):
    # Based on Hachiko's Event Handler
    def __init__(self, filename, app, loop=None):
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
        self._app = app

    async def _send_if_is_watched_file(self, event):
        if os.path.basename(event.src_path) == self.filename:
            wdlogger.info(f"File '{event.src_path}' was modified, sending new code")
            await self._app.send_code()

    async def on_modified(self, event):
        await self._send_if_is_watched_file(event)
    
    async def on_created(self, event):
        await self._send_if_is_watched_file(event)

    def dispatch(self, event):
        handler = self._method_map.get(event.event_type, None)
        if handler is not None:
            self._loop.call_soon_threadsafe(self._ensure_future, handler(event))

class AsyncFileDialog(QObject):
    file_chosen = pyqtSignal(str)

    def __init__(self, title, filters):
        super().__init__(None)
        self.dialog = QFileDialog()
        self.dialog.setWindowTitle(title)
        self.dialog.setNameFilter(filters)

    def open(self):
        self.dialog.setFileMode(QFileDialog.ExistingFile)
        self.dialog.fileSelected.connect(self.file_chosen.emit)
        
        self.dialog.open()


class FFQtApp(QWidget):
    def __init__(self, app, loop):
        super().__init__()
        self._loop = loop
        self._app = app
        self._ffgac = None
        self._fflive = None
        self._file = ""
        self._media_file = ""
        self._media_file_type = None
        self._webcam = False
        self._fs_observer = None
        self._fs_checker = None

        self._zmq_sock_live, self._zmq_sock_clean = self.zmq_create_sockets()
        self._should_send_code = {
                self._zmq_sock_live: False,
                self._zmq_sock_clean: False
                }
        loop.create_task(self.osc_start_server())
        loop.create_task(self.zmq_start())
        self._setupUI()
 
    async def zmq_start(self):
        await self.zmq_start_servers([self._zmq_sock_live, self._zmq_sock_clean])

    async def send_code(self):
        sockets = [self._zmq_sock_live, self._zmq_sock_clean]
        wdlogger.info("Sending new code")
        with open(self._file, 'r') as file:
            code = file.read()
            for socket in sockets:
                self.statusbar.showMessage("Sending new code!!")
                await socket.send_string(code)
                #if self._should_send_code[socket]:
                    #await socket.send_string(code)
                    #self._should_send_code[socket] = False

    def _setupUI(self):
        layout = QVBoxLayout()

        self.statusbar = QStatusBar(self)
        self.statusbar.showMessage("FFGlitch Livecoding")
        layout.addWidget(self.statusbar)


        self.chooseFileButton = QPushButton("Choose a script to monitor", self)
        self.chooseFileButton.clicked.connect(self.chooseFile)
        layout.addWidget(self.chooseFileButton)

        self.runBtserver = QPushButton("Run as RTMP server", self)
        self.runBtserver.clicked.connect(self.runRTMP)
        layout.addWidget(self.runBtserver)

        self.runBtloop = QPushButton("Run with video/image file", self)
        self.runBtloop.clicked.connect(self.runLoopFile)
        layout.addWidget(self.runBtloop)

        self.runBtwebcam = QPushButton("Run with webcam (Mac OS and Linux)", self)
        self.runBtwebcam.clicked.connect(self.runWebcam)
        layout.addWidget(self.runBtwebcam)

        self.forceSendCodeBt = QPushButton("Resend code", self)
        self.forceSendCodeBt.clicked.connect(self._resend_code)
        layout.addWidget(self.forceSendCodeBt)

        self.restartFFBt = QPushButton("Restart ffglitch", self)
        self.restartFFBt.clicked.connect(self.restart_ffglitch_cb)
        layout.addWidget(self.restartFFBt)
        
        # Set up window
        self.setLayout(layout)
        self.setWindowTitle('FFglitch livecoding')
        self.setGeometry(300, 300, 400, 300)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        
        for file_path in files:
            file_type = puremagic.magic_file(file_path)
            if len(file_type) > 0:
                if file_type[0].mime_type.endswith("javascript"):
                    self._watch_file(file_path)
                elif file_type[0].mime_type.startswith("video") or file_type[0].mime_type.startswith("image"):
                    self._loop.create_task(self._loopWithFile(file_path))
                else:
                    _msg = f"Unknown file format: {file_path}"
                    applogger.warning(msg)
                    self.statusbar.showMessage(msg)
            else:
                _msg = f"Unknown file: {file_path}"
                applogger.warning(msg)
                self.statusbar.showMessage(msg)

    @asyncSlot()
    async def runRTMP(self):
        await self._run_rtmp()

    async def _run_rtmp(self):
        self._media_file = ""
        self._webcam = False
        await self.run()

    @asyncSlot()
    async def runWebcam(self):
        await self._run_webcam()

    async def _run_webcam(self):
        self._media_file = ""
        self._webcam = True
        await self.run()

    async def openFileDialog(self, title, filters):
        dialog = AsyncFileDialog(title, filters)
        future = self._loop.create_future()
        dialog.file_chosen.connect(lambda file_name: future.set_result(file_name))
        dialog.open()
        file = await future
        return file

    @asyncSlot()
    async def runLoopFile(self):
        file = await self.openFileDialog("Choose a file", "All files (*)")
        if file:
            await self._loopWithFile(file)

    async def _loopWithFile(self, file):
        self._webcam = False
        self._media_file = file
        self._media_file_type = None
        try:
            file_type = puremagic.magic_file(file)
            if len(file_type) > 0:
                if file_type[0].mime_type.startswith("image"):
                    self._media_file_type = "img"
                elif file_type[0].mime_type.startswith("video"):
                    self._media_file_type = "vid"
        except puremagic.PureError:
            pass

        if self._media_file_type is None:
            _msg = f"Failed to open file {self._media_file}, is it an image/video ?"
            applogger.warning(_msg)
            self.statusbar.showMessage(_msg)
        else:
            await self.run()

    @asyncSlot()
    async def chooseFile(self):
        file = await self.openFileDialog("Choose a file", "JavaScript Files (*.js)")
        if file:
            self._watch_file(file)
    
    def _watch_file(self, file): 
        self._file = file
        self.watchdog_start()

    async def run_ffglitch(self):
        read, write = os.pipe()
        ffgac_cmd = f"\"{get_resource_path('./bin/ffgac')}\" -hide_banner -loglevel error %s -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -fcode 5 -g max -sc_threshold max -mb_type_script \"{get_resource_path('scripts/mb_type_func_live_simple.js')}\" -f rawvideo pipe:"
        status_msg = ""
        if self._media_file:
            if self._media_file_type == "vid":
                ffgac_cmd = ffgac_cmd % f"-stream_loop -1 -i \"{self._media_file}\""
            elif self._media_file_type == "img":
                ffgac_cmd = ffgac_cmd % f"-loop 1 -i \"{self._media_file}\" -t 1000000" 
            status_msg = f"Now playing: {os.path.basename(self._media_file)}"
        elif self._webcam and platform.system() in ["Linux", "Darwin"]:
            if platform.system() == "Darwin":
                ffgac_cmd = ffgac_cmd  % "-f avfoundation -r 30 -video_size 1280x720 -i default"
            else:
                ffgac_cmd = ffgac_cmd  % "-i /dev/video0"
            status_msg = f"Now in webcam mode"
        else:
            ffgac_cmd = ffgac_cmd % "-listen 1 -i rtmp://0.0.0.0:5550/live"
            status_msg = "Stream with RTMP via rtmp://127.0.0.1:5550/live ..." 

        self._ffgac = await asyncio.create_subprocess_shell(
                ffgac_cmd,
                stdout=write,
                )
        os.close(write)
        self._fflive = await asyncio.create_subprocess_shell(
                FFLIVE_CMD,
                stdin=read,
                stdout=asyncio.subprocess.PIPE,
                )
        os.close(read)
        applogger.info(status_msg)
        self.statusbar.showMessage(status_msg)
        await asyncio.gather(
                 self._ffgac.communicate(),
                 self._fflive.communicate()
                 )
       

    @asyncClose
    async def closeEvent(self, event):
        await self.stop_ffglitch()

    @asyncSlot()
    async def restart_ffglitch_cb(self):
        await self.restart_ffglitch()

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

    @asyncSlot()
    async def _resend_code(self):
        await self._send_code()

    async def _send_code(self):
        await self.send_code()

    async def zmq_start_server(self, socket):
        while True:
            message = await socket.recv_string()
            self._should_send_code[socket] = True
            if message and not message.startswith("PING"):
                reply = message
                title = "OK"
                if not reply.startswith("OK"):
                    title = "FAIL"
                notification(title, message=reply, app_name='FFLiveCoding')

    def zmq_create_sockets(self):
        context = zmq.asyncio.Context()
        cleansocket = context.socket(zmq.REP) 
        try:
            zmqlogger.info("Binding Clean script socket to port 5556")
            cleansocket.bind("tcp://*:5556")
        except zmq.error.ZMQError:
            _msg = "Failed to bind to port :5556, maybe the program is already running?"
            zmqlogger.critical(_msg)
            QMessageBox.critical(None, "FFGlitch-Livecoding Error", _msg)
            sys.exit(1)

        livesocket = context.socket(zmq.REP)
        try:
            zmqlogger.info("Binding Live script socket to port 5555")
            livesocket.bind("tcp://*:5555")
        except zmq.error.ZMQError:
            _msg = "Failed to bind to port :5555, maybe the program is already running?"
            zmqlogger.critical(_msg)
            QMessageBox.critical(None, "FFGlitch-Livecoding Error", _msg)
            sys.exit(1)

        return cleansocket, livesocket

    async def zmq_start_servers(self, sockets):
        zmqlogger.debug("Starting ZMQ listen sockets")
        await asyncio.gather(*[ self.zmq_start_server(socket) for socket in sockets])

    def watchdog_start(self):
        directory_to_watch = os.path.dirname(self._file)
        if not directory_to_watch:
            directory_to_watch = "./"

        if self._fs_observer is not None:
            wdlogger.debug("Stopping watchdog")
            self._fs_observer.stop()
    
        wdlogger.debug("Starting watchdog")
        self._fs_checker = FileChecker(os.path.basename(self._file), self, loop=self._loop)
        self._fs_observer = Observer()
        self._fs_observer.schedule(self._fs_checker, path=directory_to_watch, recursive=False)
        self._fs_observer.start()
        _msg = f"Currently watching: {self._file}"
        wdlogger.info(_msg)
        self.statusbar.showMessage(_msg)

    async def osc_start_server(self):
        context = zmq.Context()
        oscbridgesocket = context.socket(zmq.PUB)
        try:
            zmqlogger.info("OSC bridge to ffglitch serving on port 5557")
            oscbridgesocket.bind("tcp://*:5557")
        except zmq.error.ZMQError:
            QMessageBox.critical(None, "FFGlitch-Livecoding Error","Failed to bind to port :5557, maybe the program is already running?")
            sys.exit(1)

        def clean_handler(address, *args):
            osclogger.info("Cleaning")
            oscbridgesocket.send_string("/clean")

        def set_var_handler(address, *args):
            varname = args[0]
            value = args[1]
            osclogger.info(f"Setting '{varname}' to '{value}'")
            oscbridgesocket.send_string(f"/set,{varname},{value}")

        def set_watched_file(address, *args):
            filename = args[0]
            osclogger.info(f"Looping new file ${filename}")
            self._watch_file(filename)

        async def new_loop_file(address, *args):
            filename = args[0]
            osclogger.info(f"Looping new file ${filename}")
            await self._loopWithFile(filename)

        async def webcam(address, *args):
            osclogger.info("Switching to Webcam")
            await self._run_webcam()

        async def rtmp(address, *args):
            osclogger.info("Switching to RTMP")
            await self._run_rtmp()

        def sync_wrapper(handler):
            def wrapper(address, *args):
                asyncio.ensure_future(handler(address, *args))
            return wrapper

        dispatcher = Dispatcher()
        dispatcher.map("/clean",  clean_handler)
        dispatcher.map("/set", set_var_handler)
        # GUI commands
        dispatcher.map("/watch", set_watched_file)
        dispatcher.map("/loop", sync_wrapper(new_loop_file))
        dispatcher.map("/webcam", sync_wrapper(webcam))
        dispatcher.map("/rtmp", sync_wrapper(rtmp))

        osclogger.info("Starting OSC server on port 5558")
        server = osc_server.AsyncIOOSCUDPServer(("0.0.0.0", 5558), dispatcher, asyncio.get_event_loop())
        transport, protocol = await server.create_serve_endpoint()

    async def run(self):
        await self.restart_ffglitch()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    window = FFQtApp(app,loop)
    window.show()

    #loop.create_task(window.osc_start_server())
    try:
        with loop:
            applogger.debug("Starting mainloop")
            loop.run_until_complete(app_close_event.wait())
            loop.close()
    except KeyboardInterrupt:
        applogger.info("Closing... bye!")
        loop.close()
