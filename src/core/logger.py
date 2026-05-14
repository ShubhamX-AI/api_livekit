import logging
from logging.handlers import RotatingFileHandler
from multiprocessing import current_process
import sys
import json
from typing import Optional
from src.core.config import settings

# Module-level global — safe because each agent subprocess handles exactly one call.
# ContextVar was unreliable here: livekit TTS plugin spawns its own asyncio tasks
# that don't inherit the caller's context, so _room_context.get() returned None there.
_current_room: Optional[str] = None

# LiveKit names agent worker subprocesses with this value.
# See: livekit-agents ipc/job_proc_executor.py _create_process()
_LIVEKIT_JOB_PROC_NAME = "job_proc"


def set_room_context(room_name: str) -> None:
    global _current_room
    _current_room = room_name


def clear_room_context() -> None:
    global _current_room
    _current_room = None


_orig_record_factory = None


def _make_log_record(*args, **kwargs) -> logging.LogRecord:
    # Stamp call_room at record creation so it survives livekit's IPC pickle
    # before any handler (including LogQueueHandler) serializes the record.
    # A root-logger filter doesn't work here: Python's callHandlers walks up
    # to parent handlers without running parent-logger filters.
    record = _orig_record_factory(*args, **kwargs)
    record.call_room = _current_room
    return record


class ColoredFormatter(logging.Formatter):
    """Custom formatter for colored log output in development"""
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    # Format: Time - LoggerName - Level - Message (File:Line)
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging in production"""
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "file": record.filename,
            "line": record.lineno,
            "call_room": getattr(record, "call_room", None),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra"):
            log_entry.update(record.extra)

        return json.dumps(log_entry)


_logging_configured = False


def setup_logging() -> None:
    """Configure the root logger based on settings."""
    global _logging_configured, _orig_record_factory
    if _logging_configured:
        return

    root_logger = logging.getLogger()
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root_logger.setLevel(level)

    _orig_record_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(_make_log_record)
    _logging_configured = True

    # LiveKit agent subprocesses are named "job_proc". Every log record they
    # emit is forwarded to the parent via LogQueueHandler and re-emitted there.
    # Adding our own StreamHandler/FileHandler here would cause every line to
    # appear twice. Skip handlers in subprocesses; parent process owns output.
    if current_process().name == _LIVEKIT_JOB_PROC_NAME:
        return

    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_JSON_FORMAT:
        handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    else:
        handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(handler)

    if settings.LOG_FILE:
        file_handler = RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
        )
        file_handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.WARNING)


def get_logger(name: str):
    """Get a logger instance with the given name"""
    return logging.getLogger(name)

logger = get_logger("app")
