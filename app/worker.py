"""Worker for the memory service."""

import asyncio
import logging
import signal
import sys

from apps.memory.ingest.worker import run_worker
from server import config

shutdown_event = asyncio.Event()


def handle_shutdown_signal() -> None:
    """Handle shutdown signal."""
    shutdown_event.set()


async def main() -> None:
    """Run the task worker main routine."""

    config.Settings.config_logger()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown_signal)
    await run_worker(shutdown_event)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.exception("Unexpected exception occurred.")
        sys.exit(1)
