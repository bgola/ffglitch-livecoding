#!/bin/bash

IMG=$1

. .env/bin/activate

python zmqserver_livecoding_watchdog.py template.js & 
PID=$!

yt-dlp -o - "${URL}" ./bin/ffgac -i pipe: -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -fcode 5 -g max -sc_threshold max -f rawvideo pipe: | ./bin/fflive -i pipe: -s scripts/livecoding.js

kill -9 $PID
