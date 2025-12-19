"""Ingest worker for the memory system."""

import asyncio
import logging

from apps.memory.ingest.services.ingestion import ingest
from utils.queue_manager import dequeue

QUEUE_NAME = "ingestion"


async def run_worker(shutdown_event: asyncio.Event) -> None:
    """Run the worker."""

    logging.info("Started listening to queue...")

    queue_name = f"{QUEUE_NAME}"
    while not shutdown_event.is_set():
        try:
            job = await dequeue(queue_name, block_timeout=60)
            if job:
                logging.info("Processing message: %s", job)
                await ingest(job)
            else:
                logging.info("No message found")
        except Exception:
            await asyncio.sleep(0.1)

    logging.info("Finished processing ingestion.")
