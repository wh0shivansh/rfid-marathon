"""
Packaged entrypoint for UDP listener.
Ensures working directory is the executable folder when frozen.
"""

import os
import sys
from pathlib import Path
from multiprocessing import freeze_support

from dotenv import load_dotenv

import udp_listener


def _set_working_directory() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)


def main() -> None:
    freeze_support()
    _set_working_directory()
    load_dotenv()

    udp_listener.start_udp_server()


if __name__ == "__main__":
    main()
