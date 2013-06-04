import logging

from .parser import (
    igs_decoded_segments,
    BUTTON_SEGMENT, PICTURE_SEGMENT, PALETTE_SEGMENT,
)


class Palette(dict):
    def __init__(self, seg):
        log = logging.getLogger("model.Palette")
        log.info("Creating palette...")
        for color in seg["palette"]:
            assert color["color_id"] not in self
            self[color["color_id"]] = color

        for i in range(256):
            if i not in self:
                if i < 255:
                    # Seems #255 never exists
                    log.debug("Color entry #{} does not exist".format(i))

                self[i] = {
                    "color_id": i,
                    "y": 16,
                    "cb": 128,
                    "cr": 128,
                    "alpha": 0,
                }

    def __str__(self):
        return "<Palette ({} colors)>".format(len(self))


class Picture:
    def __init__(self, seg):
        self.__dict__.update(seg)
        del self.raw_data
        del self.seg_type

    def __str__(self):
        return "<Picture #{0.id} ({0.width}x{0.height})>".format(self)


class Button:
    def __init__(self, raw_data):
        self.__dict__.update(raw_data)

    def __str__(self):
        return "<Button #{0.id} ({0.x}, {0.y})>".format(self)


class BOG:
    def __init__(self, raw_data):
        self.__dict__.update(raw_data)
        self.buttons = {x["id"]: Button(x) for x in self.buttons}
        self.def_button = self.buttons[self.def_button]

    def __str__(self):
        return "<BOG ({} buttons)>".format(len(self.buttons))


class Page:
    def __init__(self, raw_data):
        self.__dict__.update(raw_data)
        self.bogs = [BOG(x) for x in self.bogs]
        self.def_button = self._find_button(self.def_button)
        self.def_activated = self._find_button(self.def_activated)

        for bog in self.bogs:
            for button in bog.buttons.values():
                nav = button.navigation
                for nav_key in list(nav.keys()):
                    nav[nav_key] = self._find_button(nav[nav_key])

    def _find_button(self, button_id):
        if button_id == 0xffff:
            return None

        for bog in self.bogs:
            for button in bog.buttons.values():
                if button.id == button_id:
                    return button

        raise KeyError("Button not found")

    def __str__(self):
        return "<Page #{} ({} BOGs)>".format(self.id, len(self.bogs))


class IGSMenu:
    def __init__(self, stream_or_filename):
        if isinstance(stream_or_filename, str):
            with open(stream_or_filename, "rb") as f:
                self.__init__(f)

            return

        self._fill_data(list(igs_decoded_segments(stream_or_filename)))

    def __str__(self):
        return "<IGSMenu ({} pages)>".format(len(self.pages))

    def _fill_data(self, parsed_data):
        self.palettes = [
            Palette(seg)
            for seg in parsed_data
            if seg["seg_type"] == PALETTE_SEGMENT
        ]
        self.pictures = {
            seg["id"]: Picture(seg)
            for seg in parsed_data
            if seg["seg_type"] == PICTURE_SEGMENT
        }
        button_segs = [x for x in parsed_data
                       if x["seg_type"] == BUTTON_SEGMENT]

        assert len(button_segs) == 1
        button_seg = button_segs[0]
        self.__dict__.update(button_seg)
        del self.raw_data
        del self.seg_type
        self.pages = {x["id"]: Page(x) for x in self.pages}
        for page in self.pages.values():
            page.palette = self.palettes[page.palette]
            for subeffect in (page.in_effects["effects"] +
                              page.out_effects["effects"]):
                subeffect["palette"] = self.palettes[subeffect["palette"]]

            for bog in page.bogs:
                for button in bog.buttons.values():
                    for states in button.states.values():
                        states["start"] = self._find_picture(states["start"])
                        states["stop"] = self._find_picture(states["stop"])

    def _find_picture(self, picture_id):
        if picture_id == 0xffff:
            return None

        return self.pictures[picture_id]
