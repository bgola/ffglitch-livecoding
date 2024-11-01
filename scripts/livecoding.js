import * as zmq from "zmq"

let zmqctx = new zmq.Context()
let zmqoscsocket = zmqctx.socket(zmq.SUB)
zmqoscsocket.setsockopt(zmq.SUBSCRIBE, "")
zmqoscsocket.connect("tcp://localhost:5557")

let zmqsocket = zmqctx.socket(zmq.REQ)
zmqsocket.setsockopt(zmq.REQ_RELAXED, 1)
zmqsocket.setsockopt(zmq.REQ_CORRELATE, 1)
zmqsocket.connect("tcp://localhost:5555")
zmqsocket.send("PING")


let globals = {};
let osc = {};

function handleOSC(message) {
  let parts = message.split(",")
  if (parts[0] == "/set") {
    let varname = parts[1]
    osc[varname] = parseFloat(parts[2])
  }
}


export function setup(args) {
  args.features = ["mv"];
}

// These functions are supposed to be defined in the livecoding file
// and sent via ZeroMQ message as a string
let setup_live = () => { };
let setup_clean = () => { };
let clean_live = () => { };
let glitch_live = (frame) => { };

// a reference to a working version of the glitch_live function
let glitch_live_working = glitch_live;

export function glitch_frame(frame) {
  let message = zmqsocket.recv_str(zmq.DONTWAIT);
  if (message) {
    try {
      eval(message)
      setup_live()
      glitch_live(frame)

      // if it didn't fail here, we use it for the next frames
      glitch_live_working = glitch_live
      zmqsocket.send("OK live")
    } catch (error) {
      zmqsocket.send(error.name + ": " + error.message)
    }
  } else {
    let oscmessage = zmqoscsocket.recv_str(zmq.DONTWAIT)
    if (oscmessage) {
      handleOSC(oscmessage)
    }
    try {
      glitch_live_working(frame)
    } catch (error) {
      console.log(error.name + ": " + error.message)
    }
  }
}
