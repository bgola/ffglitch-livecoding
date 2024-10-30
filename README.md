ffglitch-livecoding
===================

This is some very hacky way to support changing the code dynamically while running ffglitch / fflive.

To run, first create a virtualenv and install the required libraries:

```
git clone https://github.com/bgola/ffglitch-livecoding
cd ffglitch-livecoding/
python -m venv .env
. .env/bin/activate
pip install -e requirements.txt
```

Then run the watchdog script:

```
python zmqserver_livecoding_watchdog.py template.js
```

In another terminal you can run ffglitch with the scripts provided in the `scripts/` folder (check the paths for the ffglitch binaries):

```
./bin/ffgac -i somevideo_file.mp4 -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -t 1050 -fcode 5 -g max -sc_threshold max -mb_type_script scripts/mb_type_func.js -f rawvideo pipe: | ./bin/fflive -i pipe: -s scripts/livecoding.js
```

Many thanks to @ramiropolla for ffglitch! :)
