import logging


def get_logger(name: str) -> logging.Logger:
    """Return an AGPP application logger with the requested name."""

    return logging.getLogger(name)