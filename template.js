setup_clean = () => {
    globals['frame'] = 0
}

clean_live = () => {
    globals['frame'] += 1
    // cleans when saving the code
    if (globals['frame'] < 3) { return 1 };
    return 0;
}

setup_live = () => {
    globals['frame_number'] = 0;
}

glitch_live = (frame) => {
    const fwd_mvs = frame.mv?.forward;
    fwd_mvs.overflow = "truncate"
    if (!fwd_mvs) return;

    fwd_mvs.forEach((mv, row, col) => {
        if(!mv) { return };
        mv[0] = 1000
        mv[1] = 100
    })
    globals['frame_number'] += 1;
}
