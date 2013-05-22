import array

import png

YCBCR_COEFF = {
    "601": (0.299,  0.587,  0.114 ),
    "709": (0.2126, 0.7152, 0.0722),
}


def _ycbcr_to_rgb48(y, cb, cr, coeff, tv_range):
    assert y >= 0 and y <= 255
    assert cb >= 0 and cb <= 255
    assert cr >= 0 and cr <= 255

    kr, kg, kb = coeff
    offset_y = 16.0 if tv_range else 0.0
    scale_y = 255.0 / 219.0 if tv_range else 1.0
    scale_uv = 255.0 / 112.0 if tv_range else 2.0

    sy = scale_y * (y - offset_y)
    scb = scale_uv * (cb - 128)
    scr = scale_uv * (cr - 128)

    r = sy                            + scr * (1 - kr)
    g = sy - scb * (1 - kb) * kb / kg - scr * (1 - kr) * kr / kg
    b = sy + scb * (1 - kb)

    r, g, b = [max(min(x, 255.0), 0.0) for x in (r, g, b)]

    r = round(r * 256 + r)
    g = round(g * 256 + g)
    b = round(b * 256 + b)

    return (r, g, b)


def _build_rgb_palette(ycbcr_palette, coeff, tv_range):
    return {
        k: array.array("H",
            _ycbcr_to_rgb48(v["y"], v["cb"], v["cr"], coeff, tv_range) +
            (v["alpha"] * 256 + v["alpha"],)
        )
        for k, v in ycbcr_palette.items()
    }


def page_to_png(
    menu, page_index, stream,
    matrix=None, tv_range=True, state_selector=lambda _:("normal", "start"),
):
    if isinstance(stream, str):
        with open(stream, "wb") as f:
            return page_to_png(menu, page_index, f, matrix, tv_range)

    page = menu.pages[page_index]
    width = menu.width
    height = menu.height

    if not matrix:
        matrix = "709" if height >= 600 else "601"

    rgb_palette = _build_rgb_palette(
        page.palette, YCBCR_COEFF[matrix], tv_range,
    )
    image_buffer = bytearray(width * height * 8)
    with memoryview(image_buffer) as main_view:
        with main_view.cast("H") as view:
            for bog in page.bogs:
                for button in bog.buttons.values():
                    state1, state2 = state_selector(button)
                    pic = button.states[state1][state2]
                    if not pic:
                        continue

                    assert button.x >= 0 and button.y >= 0
                    assert button.x + pic.width <= width
                    assert button.y + pic.height <= height

                    for y in range(pic.height):
                        line_start = (button.y + y) * width + button.x
                        for x in range(pic.width):
                            index = pic.picture_data[y * pic.width + x]
                            color = rgb_palette[index]
                            offset = (line_start + x) * 4
                            view[offset:offset+4] = color

            writer = png.Writer(width, height, alpha=True, bitdepth=16)
            writer.write_array(stream, view)


def menu_to_png(
    menu,
    name_format="page_{0.id}_{state1}_{state2}.png",
    matrix=None,
    tv_range=True,
):
    for i in range(len(menu.pages)):
        for state1 in ("normal", "selected", "activated"):
            for state2 in ("start", "stop"):
                with open(name_format.format(
                              menu.pages[i],
                              state1=state1,
                              state2=state2,
                          ),
                          "wb") as f:
                    def _select_state(button):
                        preferences = (
                            (state1, state2),
                            (state1, "start"),
                            ("normal", state2)
                        )

                        for s1, s2 in preferences:
                            if button.states[s1][s2]:
                                return s1, s2

                        return "normal", "start"

                    page_to_png(menu, i, f, matrix, tv_range,
                                state_selector=_select_state,)
