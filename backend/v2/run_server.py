"""
Packaged entrypoint for the FastAPI backend.
Ensures working directory is the executable folder when frozen.
"""

import os
import sys
from pathlib import Path
from multiprocessing import freeze_support

import uvicorn # type: ignore

import main


def _set_working_directory() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)


def run() -> None:
    freeze_support()
    _set_working_directory()

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))

    uvicorn.run(main.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
