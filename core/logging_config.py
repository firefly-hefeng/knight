"""
Centralized logging configuration for Knight System.

Provides consistent logging setup across all modules with support for:
- Console and file handlers
- JSON formatting for production
- Log rotation
- Environment-based configuration
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class KnightLogger:
    """Knight System logger configuration."""
    
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DETAILED_FORMAT = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )
    JSON_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
    
    def __init__(
        self,
        name: str = "knight",
        level: Optional[str] = None,
        log_dir: Optional[str] = None,
        enable_file: bool = True,
        enable_console: bool = True,
        json_format: bool = False,
    ):
        """
        Initialize logger configuration.
        
        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files
            enable_file: Whether to enable file logging
            enable_console: Whether to enable console logging
            json_format: Use JSON format for production
        """
        self.name = name
        self.level = level or os.environ.get("KNIGHT_LOG_LEVEL", "INFO")
        self.log_dir = log_dir or os.environ.get("KNIGHT_LOG_DIR", "logs")
        self.enable_file = enable_file
        self.enable_console = enable_console
        self.json_format = json_format
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, self.level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup log handlers."""
        formatter = self._get_formatter()
        
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        if self.enable_file:
            self._setup_file_handler(formatter)
    
    def _get_formatter(self) -> logging.Formatter:
        """Get appropriate formatter based on configuration."""
        if self.json_format:
            return logging.Formatter(self.JSON_FORMAT)
        
        # Use detailed format in debug mode
        if self.level.upper() == "DEBUG":
            return logging.Formatter(self.DETAILED_FORMAT)
        return logging.Formatter(self.DEFAULT_FORMAT)
    
    def _setup_file_handler(self, formatter: logging.Formatter):
        """Setup rotating file handler."""
        log_path = Path(self.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Main log file with rotation
        log_file = log_path / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Error log file (errors only)
        error_log_file = log_path / f"{self.name}_error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
    
    def get_logger(self, module_name: str) -> logging.Logger:
        """
        Get a child logger for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Configured logger instance
        """
        return self.logger.getChild(module_name)


def configure_logging(
    level: Optional[str] = None,
    log_dir: Optional[str] = None,
    json_format: bool = False,
) -> KnightLogger:
    """
    Configure logging for Knight System.
    
    Args:
        level: Log level
        log_dir: Directory for log files
        json_format: Use JSON formatting
        
    Returns:
        KnightLogger instance
        
    Example:
        >>> from core.logging_config import configure_logging
        >>> logger = configure_logging(level="DEBUG")
        >>> log = logger.get_logger(__name__)
        >>> log.info("Application started")
    """
    return KnightLogger(
        level=level,
        log_dir=log_dir,
        json_format=json_format,
    )


# Global logger instance
_global_logger: Optional[KnightLogger] = None


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a module.
    
    This is a convenience function that uses the global logger configuration.
    If no global logger exists, it creates a default one.
    
    Args:
        module_name: Name of the module requesting the logger
        
    Returns:
        Logger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = configure_logging()
    return _global_logger.get_logger(module_name)
