import argparse
import os
import sys
import traceback
from contextlib import contextmanager
import functools
import logging

from . import IGSMenu
from .export import menu_to_png, YCBCR_COEFF
from . import debugging

ENTRYPOINT = "igstopng"


@contextmanager
def _error_msg(msg, verbose, debug):
    try:
        yield
    except:
        if debug:
            raise

        if verbose:
            traceback.print_exc()

        print("Error:", msg, file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog=ENTRYPOINT,
        description="Export bluray IGS menu to PNG images",
    )
    parser.add_argument("files", metavar="file", nargs="+")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show detailed information on error",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="attach pdb on error",
    )
    parser.add_argument(
        "-m", "--matrix", choices=YCBCR_COEFF.keys(),
        help="specify YUV matrix of menu file. If skipped, it will be auto-" +
             "detected from height of the menu.",
    )
    parser.add_argument(
        "--full-range", dest="tv_range", action="store_false",
        help="specify that menu file is in full range. Default is TV range.",
    )
    args = parser.parse_args()
    if args.debug:
        debugging.setup()
        logging.basicConfig(level=logging.DEBUG)

    m = functools.partial(_error_msg, verbose=args.verbose, debug=args.debug)

    for name in args.files:
        if not os.path.isfile(name):
            print("Error: {} is not found".format(name), file=sys.stderr)
            continue

        with m("Failed to parse {}".format(name)):
            menu = IGSMenu(name)

        prefix, _ = os.path.splitext(name)
        with m("Unable to generate image for {}".format(name)):
            menu_to_png(
                menu, prefix + "_{0.id}_{state1}_{state2}.png",
                matrix=args.matrix,
                tv_range=args.tv_range,
            )


if __name__ == "__main__":
    main()
