import logging

_logger = logging.getLogger("fiscal-service")


def get_logger(name: str = "fiscal-service") -> logging.Logger:
    return logging.getLogger(name)
