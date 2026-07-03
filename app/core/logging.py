import logging
import sys
from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Default handler from python logging to loguru.
    See: https://loguru.readthedocs.io/en/stable/resources/recipes.html#integrating-with-redirection-re-routing-of-warnings-and-logging-std
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(debug: bool = False):
    # Remove default handler
    logger.remove()

    # Determine log level
    log_level = "DEBUG" if debug else "INFO"

    # Add console logger
    logger.add(
        sys.stdout,
        enqueue=True,
        backtrace=True,
        diagnose=debug,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # Intercept standard library logging calls
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Re-route specific libraries if they are too noisy
    for logger_name in ("uvicorn.access", "uvicorn.error", "fastapi"):
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logger.info("Logging initialized successfully using Loguru.")
