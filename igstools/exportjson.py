import json
import base64
from io import BytesIO

from .export import picture_to_png, matrix_from_menu_height


def menu_to_json(
    menu,
    stream,
    matrix=None,
    tv_range=True,
):
    if isinstance(stream, str):
        with open(stream, "w") as f:
            return menu_to_json(menu, f, matrix, tv_range)

    if not matrix:
        matrix = matrix_from_menu_height(menu.height)

    json_obj = {
        "version": 1,
        "pictures": {},
        "pages": {p.id: p.raw_data for p in menu.pages.values()},
        "width": menu.width,
        "height": menu.height,
    }
    for pic in menu.pictures.values():
        json_obj["pictures"][pic.id] = {
            "width": pic.width,
            "height": pic.height,
            "decoded_pictures": {},
        }

    for page in menu.pages.values():
        for bog in page.bogs:
            for button in bog.buttons.values():
                for state1 in button.states.values():
                    for pic in state1.values():
                        if pic is None or isinstance(pic, int):
                            continue

                        pictures = json_obj["pictures"][pic.id]["decoded_pictures"]
                        palette_id = page.palette_id
                        if palette_id not in pictures:
                            buffer = BytesIO()
                            picture_to_png(
                                pic, page.palette, buffer,
                                matrix=matrix, tv_range=tv_range,)
                            pictures[palette_id] = base64.b64encode(buffer.getvalue()).decode("utf-8")

    json.dump(json_obj, stream, indent=2)

