"""Worker for the memory service."""

import logging

from server import config

config.Settings.config_logger()

logging.info("Worker started")
