// ./bin/fflive -i CEP00109_mpeg4.avi -s scripts/mpeg4/mv_average.js
import * as zmq from "zmq";

const CANDIDATE_MB_TYPE_INTRA = (1 << 0);
const CANDIDATE_MB_TYPE_INTER = (1 << 1);

class Command {
  constructor() {
  }

  run(mb_types, nb_frames) {
    if (!nb_frames)
      return;

    const mb_height = mb_types.length;
    const mb_width = mb_types[0].length;

    for (let mb_y = 0; mb_y < mb_height; mb_y++)
      for (let mb_x = 0; mb_x < mb_width; mb_x++)
        mb_types[mb_y][mb_x] = CANDIDATE_MB_TYPE_INTRA;
  }
}

export function setup(args) {
  command = new Command();
}

let zmqctx = new zmq.Context();

let zmqoscsocket = zmqctx.socket(zmq.SUB)
zmqoscsocket.setsockopt(zmq.SUBSCRIBE, "")
zmqoscsocket.connect("tcp://localhost:5557")

let zmqsocket = zmqctx.socket(zmq.REQ);
zmqsocket.connect("tcp://localhost:5556");
zmqsocket.send("PING clean")

let command;
let globals = {};
let osc = {};

let nb_frames = null;
let setup_clean = () => { return 0 };
let clean_live = () => { return null };
let clean_live_working = () => clean_live;

let setup_live = () => { return 0 };
let glitch_live = () => { return 0 };

let clean_from_osc = false;
function handleOSC(message) {
  let parts = message.split(",")
  if (parts[0] == "/set") {
    let varname = parts[1]
    osc[varname] = parseFloat(parts[2])
  } else if (parts[0] == "/clean") {
    clean_from_osc = true;
  }
}

export function mb_type_func(args) {
  let msg;
  try {
	  msg = zmqsocket.recv_str(zmq.DONTWAIT);
  } catch {
  };
  if (msg) {
    try {
      eval(msg)
      setup_clean()
      nb_frames = clean_live()
      clean_live_working = clean_live
      zmqsocket.send("OK clean")
    } catch (error) {
      zmqsocket.send(error.name + ": " + error.message)
    }
  } else {
    let oscmessage = zmqoscsocket.recv_str(zmq.DONTWAIT)
    while (oscmessage) {
      handleOSC(oscmessage)
      oscmessage = zmqoscsocket.recv_str(zmq.DONTWAIT)
    }
    try {
      nb_frames = clean_live_working();
    } catch (error) {
      console.log(error.name + ": " + error.message)
    }
  }
  if (nb_frames == 0) { nb_frames = null }
  if (clean_from_osc) { 
    clean_from_osc = false 
    command.run(args.mb_types, true);
  } else {
    command.run(args.mb_types, nb_frames);
  }
}
