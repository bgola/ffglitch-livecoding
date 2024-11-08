// setup_clean is called once when you save the file

setup_clean = () => {
    globals.frame = 0
}

// clean_live is called every frame
clean_live = () => {
    globals.frame += 1
    // cleans when saving the code
    if (globals.frame == 1) { return 1 };
    return 0;
}


// setup_live is called once when you save the file
setup_live = () => {
    globals.frame = 0;
}

// glitch_live is called every frame
glitch_live = (frame) => {
    const fwd_mvs = frame.mv?.forward
    if (!fwd_mvs) return;
    fwd_mvs.overflow = "truncate"
    
    let rows = fwd_mvs.height
    let cols = fwd_mvs.width
    let framenumber = globals.frame
    fwd_mvs.forEach((mv, row, col) => {
        if(!mv) { return };
        // normalized values for row and col (from 0 to 1)
        let x = col/cols
        let y = row/rows

        // Send OSC messages to port 5558 to set osc. variables:
        // for example, to set the osc.someValue variable to 10.0:
        //     /set,someValue,10.0

        mv[0] += (y-0.5) * osc.someValue
        mv[1] += (x-0.5) * osc.anotherValue
    })
    globals.frame += 1
}