ffglitch-livecoding
===================

This is some very hacky way to support changing the code dynamically while running [ffglitch](https://github.com/ramiropolla/ffglitch-core/).

If you don't know what ffglitch is, check the [webpage](https://ffglitch.org/) and the WIP [tutorial](https://github.com/ramiropolla/ffglitch-scripts/tree/main/tutorial)

To run, first create a virtualenv and install the required libraries:

```bash
git clone https://github.com/bgola/ffglitch-livecoding
cd ffglitch-livecoding/
python -m venv .env
. .env/bin/activate
pip install -r requirements.txt
```

If you use GNU/Linux you can also install `notify-send` from pip to have some nice visual feedback when you save the code:

`pip install notify-send`

Make a copy of the `template.js` file.

Then run the watchdog script pointing it to the file you just copied:

```bash
. .env/bin/activate
python zmqserver_livecoding_watchdog.py your-file.js
```

I recommend to download the latest release of ffglitch from [ffglitch.org](https://ffglitch.org/), extracting the files in your ffglitch-livecoding copy and renaming the ffglitch folder to `bin/`.

In another terminal you can run ffglitch with the scripts provided in the `scripts/` folder (**check the paths for the ffglitch binaries**):

```bash
./bin/ffgac -i somevideo_file.mp4 -vcodec mpeg4 -mpv_flags +nopimb+forcemv -qscale:v 1 -t 1050 -fcode 5 -g max -sc_threshold max -mb_type_script scripts/mb_type_func_live.js -f rawvideo pipe: | ./bin/fflive -i pipe: -s scripts/livecoding.js
```

Now open the file you copied from the template, edit and save it to start live coding.

Sending OSC messages
====================

The watchdog script is listening to OpenSoundControl messages in port `5558`.

There are two supported messages:

- `/clean`: this will clean the frame (and continue to apply the current script)
- `/set, "varname", 10.0`: you can set any variable using the `/set` command. Those are accessible in the livecoding script via the `osc` object. Check the `template.js` for an example.

A example in SuperCollider:

```
n = NetAddr("127.0.0.1", 5558);

n.sendMsg("/set", "someValue", 10.0.rand2);
n.sendMsg("/set", "anotherValue", 10.0.rand2);
n.sendMsg("/clean")
```

Thanks
======

Many thanks to [Ramiro](https://github.com/ramiropolla/) for ffglitch! And to [S4NTP](https://s4ntp.org) for testing this concept with me :-)
