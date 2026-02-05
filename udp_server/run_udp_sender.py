"""
Packaged entrypoint for UDP sender (FastAPI).
Ensures working directory is the executable folder when frozen.
"""

import os
import sys
from pathlib import Path
from multiprocessing import freeze_support

from dotenv import load_dotenv
import uvicorn

import udp_sender


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

    host = os.getenv("BIND_HOST", "0.0.0.0")
    port = int(os.getenv("BIND_PORT", "6001"))

    uvicorn.run(udp_sender.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
