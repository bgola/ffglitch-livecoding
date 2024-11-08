#!/bin/bash

IMG=$1
FRAMES=$2

if [ "$FRAMES" == "" ]
then
	FRAMES=max
fi



. .env/bin/activate

python zmqserver_livecoding_watchdog.py template.js & 
PID=$!

yt-dlp -o - "${URL}" ./bin/ffgac -i pipe: -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -fcode 5 -g ${FRAMES} -sc_threshold max -mb_type_script scripts/mb_type_func_live_simple.js  -f rawvideo pipe: | ./bin/fflive -i pipe: -s scripts/livecoding.js

kill -9 $PID
