from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import zmq
import os
import sys
import time

try:
    from notify import notification
except:
    notification = lambda title, message, app_name: print(f"Result: {title}\n\t{message}")

class FileChecker(FileSystemEventHandler):
    def __init__(self, filename, *args,**kwargs):
        super(FileChecker, self).__init__(*args, **kwargs)
        self.filename = filename
        self.modified = False

    def on_modified(self, event):
        if os.path.basename(event.src_path) == self.filename:
            self.modified = True

    def on_created(self, event):
        if os.path.basename(event.src_path) == self.filename:
            self.modified = True

def start_zmq_server(checker):
    last_code = '"NOTHING"'
    context = zmq.Context()
    livesocket = context.socket(zmq.REP) 
    livesocket.bind("tcp://*:5555")
    
    cleansocket = context.socket(zmq.REP) 
    cleansocket.bind("tcp://*:5556")

    while True:
        send = False
        if checker.modified:
            checker.modified = False
            last_code = open(file).read()
            send = True

        for socket in [cleansocket, livesocket]:
            try:
                message = socket.recv_string(zmq.DONTWAIT)
            except:
                message = None
            if message and not message.startswith("PING"):
                reply = message
                title = "OK"
                if not reply.startswith("OK"):
                    title = "FAIL"
                notification(title, message=reply, app_name='FFLiveCoding')
            if send:
                socket.send_string(last_code) 
        time.sleep(1/20)


file = sys.argv[1]
directory_to_watch = os.path.dirname(file)
if not directory_to_watch:
    directory_to_watch = "./"

if __name__ == "__main__":
    checker = FileChecker(os.path.basename(file))
    observer = Observer()
    observer.schedule(checker, path=directory_to_watch, recursive=False)
    observer.start()
    start_zmq_server(checker)
