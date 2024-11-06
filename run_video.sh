#!/bin/bash

VID=$1

. .env/bin/activate

python zmqserver_livecoding_watchdog.py  template.js & 
PID=$!

./bin/ffgac -stream_loop -1 -i "${VID}" -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -fcode 5 -g max -sc_threshold max -f rawvideo pipe: | ./bin/fflive -i pipe: -s scripts/livecoding.js

kill -9 $PID
