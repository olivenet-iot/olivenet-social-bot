"""
Olivenet Social Bot - Centralized Logging System

Structured logging with:
- Console output (colored)
- File rotation (daily)
- Agent-specific loggers
- Performance tracking
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional
import json


# Color codes for console output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        record.levelname = f"{color}{record.levelname}{Colors.RESET}"
        record.name = f"{Colors.CYAN}{record.name}{Colors.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging to files."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "agent"):
            log_data["agent"] = record.agent
        if hasattr(record, "action"):
            log_data["action"] = record.action
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "post_id"):
            log_data["post_id"] = record.post_id
        if hasattr(record, "platform"):
            log_data["platform"] = record.platform
        if hasattr(record, "error_type"):
            log_data["error_type"] = record.error_type

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    log_dir: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Setup centralized logging for the application.

    Args:
        log_dir: Directory for log files
        console_level: Logging level for console output
        file_level: Logging level for file output
        max_bytes: Max size per log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Root logger instance
    """
    # Default log directory
    if log_dir is None:
        log_dir = Path("/home/ubuntu/olivenet-social-bot/logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger("olivenet")
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    console_handler.setFormatter(ColoredFormatter(console_format, datefmt="%H:%M:%S"))
    root_logger.addHandler(console_handler)

    # Main log file (rotating by size)
    main_log = log_dir / "olivenet.log"
    file_handler = RotatingFileHandler(
        main_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Error log (separate file for errors only)
    error_log = log_dir / "errors.log"
    error_handler = RotatingFileHandler(
        error_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # Agent activity log (daily rotation)
    agent_log = log_dir / "agents.log"
    agent_handler = TimedRotatingFileHandler(
        agent_log,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    agent_handler.setLevel(logging.INFO)
    agent_handler.setFormatter(JSONFormatter())

    # Create agent-specific logger
    agent_logger = logging.getLogger("olivenet.agents")
    agent_logger.addHandler(agent_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (e.g., "planner", "creator")

    Returns:
        Logger instance
    """
    return logging.getLogger(f"olivenet.{name}")


def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    Get a logger specifically for agent activities.

    Args:
        agent_name: Name of the agent (e.g., "planner", "creator")

    Returns:
        Logger instance with agent context
    """
    return logging.getLogger(f"olivenet.agents.{agent_name}")


class AgentLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that automatically adds agent context.

    Usage:
        logger = AgentLoggerAdapter("planner")
        logger.info("Processing topic", extra={"action": "suggest_topic"})
    """

    def __init__(self, agent_name: str, logger: Optional[logging.Logger] = None):
        if logger is None:
            logger = get_agent_logger(agent_name)
        super().__init__(logger, {"agent": agent_name})

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["agent"] = self.extra["agent"]
        kwargs["extra"] = extra
        return msg, kwargs

    def log_action(
        self,
        action: str,
        message: str,
        duration_ms: Optional[float] = None,
        post_id: Optional[int] = None,
        success: bool = True,
        **kwargs
    ):
        """Log an agent action with structured data."""
        extra = {
            "action": action,
            "success": success,
            **kwargs
        }
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms
        if post_id is not None:
            extra["post_id"] = post_id

        level = logging.INFO if success else logging.ERROR
        self.log(level, message, extra=extra)

    def log_api_call(
        self,
        api_name: str,
        endpoint: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log an API call for performance tracking."""
        extra = {
            "action": "api_call",
            "api": api_name,
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "success": success,
        }
        if error:
            extra["error"] = error

        level = logging.INFO if success else logging.WARNING
        msg = f"{api_name} API call to {endpoint} ({duration_ms:.0f}ms)"
        self.log(level, msg, extra=extra)


class PerformanceTimer:
    """
    Context manager for timing operations.

    Usage:
        with PerformanceTimer(logger, "generate_content") as timer:
            # ... operation ...
        # Automatically logs duration
    """

    def __init__(
        self,
        logger: AgentLoggerAdapter,
        action: str,
        post_id: Optional[int] = None,
        **extra_fields
    ):
        self.logger = logger
        self.action = action
        self.post_id = post_id
        self.extra_fields = extra_fields
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        success = exc_type is None

        if success:
            self.logger.log_action(
                self.action,
                f"{self.action} completed in {self.duration_ms:.0f}ms",
                duration_ms=self.duration_ms,
                post_id=self.post_id,
                success=True,
                **self.extra_fields
            )
        else:
            self.logger.log_action(
                self.action,
                f"{self.action} failed after {self.duration_ms:.0f}ms: {exc_val}",
                duration_ms=self.duration_ms,
                post_id=self.post_id,
                success=False,
                error_type=exc_type.__name__ if exc_type else None,
                **self.extra_fields
            )

        return False  # Don't suppress exceptions


# Initialize logging on module import
_root_logger = None

def init_logging():
    """Initialize logging system (call once at application startup)."""
    global _root_logger
    if _root_logger is None:
        _root_logger = setup_logging()
    return _root_logger


# Convenience functions
def debug(msg: str, **kwargs):
    get_logger("main").debug(msg, **kwargs)

def info(msg: str, **kwargs):
    get_logger("main").info(msg, **kwargs)

def warning(msg: str, **kwargs):
    get_logger("main").warning(msg, **kwargs)

def error(msg: str, **kwargs):
    get_logger("main").error(msg, **kwargs)

def critical(msg: str, **kwargs):
    get_logger("main").critical(msg, **kwargs)
