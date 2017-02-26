import vapoursynth as vs
import mvsfunc as mvf
import functools


def fade_text_mask(src, lthr=225, cthr=2, expand=2, fade_nums=8, apply_range=None):
    """
    A very very simple textmask creating function to handle fading text on screen
    Version: 0.2.0
    :param src: source clip, vs.YUV
    :param lthr: <int> threshold of luma in 8bit scale. Default:225
    :param cthr: <int> threshold of chroma in 8bit scale. Default:2
    :param expand: <int> times of expansion of textmask. Default:2
    :param fade_nums: <int, list or tuple> the length of fading. Use list or tuple to specify fade-in and fade-out
                       separately. Default:8
    :param apply_range: <list or tuple> range of src clip to apply mask.
    :return: mask clip, vs.GRAY
    """
    core = vs.get_core()
    depth = src.format.bits_per_sample
    color_family = src.format.color_family
    w = src.width
    h = src.height
    func_name = 'Fade Text Mask'

    if not isinstance(src, vs.VideoNode):
        raise TypeError(func_name + ': src is not a video clip.')
    if color_family is not vs.YUV:
        raise TypeError(func_name + ': src should be a YUV clip.')
    if depth > 8:
        src = mvf.Depth(src, 8)

    y = core.std.ShufflePlanes(src, 0, vs.GRAY)
    u = core.std.ShufflePlanes(src, 1, vs.GRAY)
    v = core.std.ShufflePlanes(src, 2, vs.GRAY)

    try:
        u = core.resize.Bicubic(u, w, h, src_left=0.25)
        v = core.resize.Bicubic(v, w, h, src_left=0.25)
    except vs.Error:
        u = mvf.Depth(core.fmtc.resample(u, w, h, sx=0.25), 8)
        v = mvf.Depth(core.fmtc.resample(v, w, h, sx=0.25), 8)

    expr = "x {lthr} > y 128 - abs {cthr} < and z 128 - abs {cthr} < and 255 0 ?".format(lthr=lthr, cthr=cthr)
    tmask = core.std.Expr([y, u, v], expr)
    if expand > 1:
        for i in range(expand):
            tmask = core.std.Maximum(tmask)

    frame_count = src.num_frames

    def shift_backward(n, clip, num):
        if n + num > frame_count - 1:
            return clip[frame_count - 1]
        else:
            return clip[n + num]

    def shift_forward(n, clip, num):
        if n - num < 0:
            return clip[0]
        else:
            return clip[n - num]

    if isinstance(fade_nums, int):
        in_num = fade_nums
        out_num = fade_nums
    elif isinstance(fade_nums, (list, tuple)):
        if len(fade_nums) != 2:
            raise ValueError(func_name + ': incorrect fade_nums setting.')
        in_num = fade_nums[0]
        out_num = fade_nums[1]
    else:
        raise TypeError(func_name + ': fade_num can only be int, list or tuple.')

    fade_in = core.std.FrameEval(tmask, functools.partial(shift_backward, clip=tmask, num=in_num))
    fade_out = core.std.FrameEval(tmask, functools.partial(shift_forward, clip=tmask, num=out_num))
    combined = core.std.Expr([tmask, fade_in, fade_out], "x y max z max")

    if apply_range is not None:
        if not isinstance(apply_range, (list, tuple)):
            raise TypeError(func_name + ': apply range can only be list or tuple')
        elif len(apply_range) != 2:
            raise ValueError(func_name + ': incorrect apply range setting.')
        else:
            try:
                blank_clip = core.std.BlankClip(tmask)
                if 0 in apply_range:
                    combined = combined[apply_range[0]:apply_range[1]] + blank_clip[apply_range[1]:]
                elif frame_count in apply_range:
                    combined = blank_clip[0:apply_range[0]] + combined[apply_range[0]:apply_range[1]]
                else:
                    combined = (blank_clip[0:apply_range[0]] + combined[apply_range[0]:apply_range[1]]
                                + blank_clip[apply_range[1]:])
            except vs.Error:
                raise ValueError(func_name + ': incorrect apply range setting. Possible end less than start.')

    if depth > 8:
        scale = ((1 << depth) - 1) // 255
        out_depth = "vs.GRAY{out_depth}".format(out_depth=depth)
        combined = core.std.Expr(combined, "x " + str(scale) + " *", eval(out_depth))

    return combined
