ffglitch-livecoding
===================

This is some very hacky way to support changing the code dynamically while running [ffglitch](https://github.com/ramiropolla/ffglitch-core/).

If you don't know what ffglitch is, check the [webpage](https://ffglitch.org/) and the WIP [tutorial](https://github.com/ramiropolla/ffglitch-scripts/tree/main/tutorial)

**Note:** there is a bug in the current release of ffglitch and it might not work with ffglitch-livecoding on Mac OS or Windows. 
Builds with the bugfix (thanks to @ramiropolla) are available here at https://bgo.la/ffglitch-0.10.2-bugfix-builds/

In that URL you also find experimental builds of ffglitch-livecoding that should work on your OS (Mac OS X minimum version is 13.0).

Running
=======

To run, you can either download the build from the link above or follow these steps:

First create a virtualenv and install the required libraries:

```bash
git clone https://github.com/bgola/ffglitch-livecoding
cd ffglitch-livecoding/
python -m venv .env
. .env/bin/activate
pip install -r requirements.txt
```

If you use GNU/Linux you can also install `notify-send` from pip to have some nice visual feedback when you save the code:

`pip install notify-send`

Download the latest release of ffglitch from [ffglitch.org](https://ffglitch.org/), extract the files in your `ffglitch-livecoding` directory and renaming the ffglitch folder to `bin/`.

Now, run the python script to open the GUI: 

```bash
. .env/bin/activate
python zmqserver_livecoding_watchdog.py
```

Make a copy of the `template.js` file, drag and drop it into ffglitch-livecoding window (or select it using the button).

Choose a video or image file, then open the file you copied from the template, edit and save it to start live coding.

RTMP mode
=========

When running in RTMP server mode, ffglitch-livecoding will run ffglitch listening in port 5550 for RTMP connections. This allows you to stream directly from OBS or any other software
that supports RTMP, and then glitch that stream. 

Notice that when you enable RTMP mode, nothing will show up until you start streaming.

For OBS, go to the settings->streaming and set the server to `rtmp://127.0.0.1:5550` and start streaming, you should see the ffglitch stream right after.

Sending OSC messages
====================

The watchdog script is listening to OpenSoundControl messages in port `5558`.

Supported messages:

- `/loop, "<path.mp4>"`: loads a new file and loops it (video or image)
- `/rtmp`: runs in RTMP mode (see section above) 
- `/watch, "<path.js>"`: starts watching a new JavaSript file, useful if you want to switch between effects quickly.
- `/clean`: this will clean the frame (and continue to apply the current script)
- `/set, "varname", 10.0`: you can set any variable using the `/set` command. Those are accessible in the livecoding script via the `osc` object. Check the `template.js` for an example.

A example in SuperCollider:

```supercollider
n = NetAddr("127.0.0.1", 5558);

n.sendMsg("/loop", "/tmp/myvideo.mp4");
n.sendMsg("/set", "someValue", 10.0.rand2);
n.sendMsg("/set", "anotherValue", 10.0.rand2);
n.sendMsg("/clean")
```

Thanks
======

Many thanks to [Ramiro](https://github.com/ramiropolla/) for ffglitch! And to [S4NTP](https://s4ntp.org) for testing this concept with me :-)
