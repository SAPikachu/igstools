# References:
# Muxer/Demuxer: http://patches.libav.org/patch/22445/
# Decoder:       http://patches.libav.org/patch/22446/
import struct
import io

PALETTE_SEGMENT = 0x14
PICTURE_SEGMENT = 0x15
BUTTON_SEGMENT  = 0x18
DISPLAY_SEGMENT = 0x80


def _eof_aware_read(stream, length, fail_on_no_data=False):
    ret = stream.read(length)
    if not ret:
        if fail_on_no_data:
            raise EOFError()

        return None

    if len(ret) < length:
        raise EOFError()

    return ret


def unpack_from_stream(fmt, stream):
    data = _eof_aware_read(stream, struct.calcsize(fmt))
    if not data:
        return None

    return struct.unpack(fmt, data)


def igs_raw_segments(stream):
    # All integers are in big-endian
    # ["IG"] [u32 pts] [u32 dts] [u8 seg_type] [u16 seg_length]
    while True:
        header_tuple = unpack_from_stream(">2sIIBH", stream)
        if not header_tuple:
            return

        magic, pts, dts, seg_type, seg_length = header_tuple
        if magic != b"IG":
            raise ValueError("Invalid segment header")

        raw_data = stream.read(seg_length)
        if len(raw_data) < seg_length:
            raise EOFError()

        yield {
            "pts": pts,
            "dts": dts,
            "seg_type": seg_type,
            "raw_data": raw_data,
        }


def parse_palette_segment(stream):
    ret = {
        "palette": [],
    }

    # 2 unknown bytes, not id
    stream.read(2)

    while True:
        entry_data = unpack_from_stream("BBBBB", stream)
        if not entry_data:
            break

        color_id, y, cr, cb, alpha = entry_data
        ret["palette"].append({
            "color_id": color_id,
            "y": y,
            "cr": cr,
            "cb": cb,
            "alpha": alpha,
        })

    return ret


def parse_picture_segment(stream):
    # [u16 oid] [u8 ver] [u8 seq_desc] [u24 rle_bitmap_len *]
    # [u16 width] [u16 height]
    picture_id, ver, seq_desc, len1, len2, len3, width, height = \
        unpack_from_stream(">HBBBBBHH", stream)

    rle_bitmap_len = (len1 << 16) | (len2 << 8) | len3

    # Stored length includes width and height
    rle_bitmap_len -= 4
    return {
        "id": picture_id,
        "ver": ver,
        "seq_desc": seq_desc,
        "is_continuation": not bool(seq_desc & 0x80),
        "width": width,
        "height": height,
        "rle_bitmap_len": rle_bitmap_len,
        "rle_bitmap_data": stream.read(),
    }


def parse_button_segment(stream):
    # [u16 width] [u16 height] [u8 framerate_id] [u16 unkwown] [u8 flags]
    # [u32 in_time] [u32 to]
    width, height, framerate_id, _, flags, in_time, to = \
        unpack_from_stream(">HHBHBII", stream)

    if to == 0:
        # Ten more byte skipped (output generated by TMpegEnc Authoring 5)
        _eof_aware_read(stream, 10)

    page_count = ord(stream.read(1))
    ret = {
        "width": width,
        "height": height,
        "framerate_id": framerate_id,
        "flags": flags,
        "in_time": in_time,
        "to": to,
        "pages": [],
    }
    for i in range(page_count):
        # [u8 page_id] [u8 unknown] [u64 uo] [u32 in/out_effects count]
        # [u8 framerate_divider] [u16 def_button] [u16 def_activated]
        # [u8 palette] [u8 bog_count]
        page_id, _, uo, effect_count, framerate_divider, def_button, \
            def_activated, palette, bog_count = \
            unpack_from_stream(">BBQIBHHBB", stream)

        cur_page = {
            "id": page_id,
            "uo": uo,
            "effect_count": effect_count,
            "framerate_divider": framerate_divider,
            "def_button": def_button,
            "def_activated": def_activated,
            "palette": palette,
            "bogs": [],
        }
        for j in range(bog_count):
            # [u16 def_button] [u8 button_count]
            bog_def_button, button_count = unpack_from_stream(">HB", stream)
            cur_bog = {
                "def_button": bog_def_button,
                "buttons": [],
            }
            for k in range(button_count):
                # f is u8, others are all u16
                button_id, v, f, x, y, nu, nd, nl, nr, \
                    picstart_normal, picstop_normal, flags_normal, \
                    picstart_selected, picstop_selected, flags_selected, \
                    picstart_activated, picstop_activated, cmds_count = \
                    unpack_from_stream(">HHB" + "H" * 15, stream)

                cur_bog["buttons"].append({
                    "id": button_id,
                    "v": v,
                    "f": f,
                    "x": x,
                    "y": y,
                    "navigation": {
                        "up": nu,
                        "down": nd,
                        "left": nl,
                        "right": nr,
                    },
                    "states": {
                        "normal": {
                            "start": picstart_normal,
                            "stop": picstop_normal,
                            "flags": flags_normal,
                        },
                        "selected": {
                            "start": picstart_selected,
                            "stop": picstop_selected,
                            "flags": flags_selected,
                        },
                        "activated": {
                            "start": picstart_activated,
                            "stop": picstop_activated,
                        },
                    },
                    # 3 u32 for each command
                    "commands": [unpack_from_stream(">III", stream)
                                 for x in range(cmds_count)],
                })

            cur_page["bogs"].append(cur_bog)

        ret["pages"].append(cur_page)

    return ret


def igs_parsing_segments(stream):
    ops = {
        PALETTE_SEGMENT: parse_palette_segment,
        PICTURE_SEGMENT: parse_picture_segment,
        BUTTON_SEGMENT: parse_button_segment,
        DISPLAY_SEGMENT: lambda x: {},
    }
    for seg in igs_raw_segments(stream):
        op = ops[seg["seg_type"]]
        seg.update(op(io.BytesIO(seg["raw_data"])))
        yield seg


def decode_rle(stream, width, height):
    out_stream = io.BytesIO()
    pixels_decoded = 0
    while True:
        color = stream.read(1)
        if not color:
            break

        run = 1

        if color == b"\x00":
            flags = ord(_eof_aware_read(stream, 1, True))
            run = flags & 0x3f
            if flags & 0x40:
                run = (run << 8) + ord(_eof_aware_read(stream, 1, True))

            color = (_eof_aware_read(stream, 1, True)
                     if (flags & 0x80) else b"\x00")

        assert run >= 0
        if run > 0:
            out_stream.write(color * run)
            pixels_decoded += run
        else:
            # New line
            if pixels_decoded % width != 0:
                raise ValueError("Incorrect number of pixels")

    decoded_data = out_stream.getvalue()
    expected_size = width * height
    actual_size = len(decoded_data)
    if actual_size < expected_size:
        raise EOFError()
    elif actual_size > expected_size:
        raise ValueError("Expected {} pixels, got {}".format(
            expected_size, actual_size
        ))

    return decoded_data


def igs_decoded_segments(stream):
    pending_pictures = []
    for seg in igs_parsing_segments(stream):
        if seg["seg_type"] != PICTURE_SEGMENT:
            yield seg
            continue

        pending_pictures.append(seg)
        cur_data_length = sum(len(x["rle_bitmap_data"])
                              for x in pending_pictures)
        pic_data_length = pending_pictures[0]["rle_bitmap_len"]
        if cur_data_length < pic_data_length:
            continue

        if cur_data_length > pic_data_length:
            raise ValueError("Picture data is too long")

        new_picture = pending_pictures[0].copy()
        new_picture["picture_data"] = decode_rle(
            io.BytesIO(b"".join([x["rle_bitmap_data"]
                       for x in pending_pictures])),
            new_picture["width"],
            new_picture["height"],
        )
        del new_picture["rle_bitmap_data"]
        del new_picture["rle_bitmap_len"]
        del new_picture["is_continuation"]
        pending_pictures.clear()
        yield new_picture

    if pending_pictures:
        raise EOFError()
