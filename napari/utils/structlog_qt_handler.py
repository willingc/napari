"""Handler for Qt messages that routes them to structlog."""

import logging

import structlog
from qtpy.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

# Map Qt log levels to Python logging levels
QT_LOG_LEVEL_MAP = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


class QtStructLogHandler:
    """
    Handler to capture Qt log messages and redirect them to structlog.
    """

    def __init__(self, logger=None):
        """
        Initialize the Qt message handler with a structlog logger.

        Args:
            logger: A structlog logger instance. If None, a new one will be created.
        """
        if logger is None:
            self.logger = structlog.get_logger()
        else:
            self.logger = logger

        # Install Qt message handler
        qInstallMessageHandler(self.handle_qt_message)

    def handle_qt_message(
        self, msg_type: QtMsgType, context: QMessageLogContext, message: str
    ) -> None:
        """
        Handle Qt log messages and forward them to structlog.

        Args:
            msg_type: Qt message type (debug, info, warning, critical, fatal)
            context: Qt message context with file, line, function, and category information
            message: The log message
        """
        # Get corresponding Python log level
        log_level = QT_LOG_LEVEL_MAP.get(msg_type, logging.INFO)

        # Create structured log data
        log_data = {
            'qt_category': context.category.decode()
            if context.category
            else None,
            'qt_file': context.file.decode() if context.file else None,
            'qt_line': context.line if context.line != -1 else None,
            'qt_function': context.function.decode()
            if context.function
            else None,
            'qt_message_type': str(msg_type).split('.')[-1],
        }

        # Remove None values for cleaner output
        log_data = {k: v for k, v in log_data.items() if v is not None}

        # Log with appropriate level using structlog
        if log_level == logging.DEBUG:
            self.logger.debug(message, **log_data)
        elif log_level == logging.INFO:
            self.logger.info(message, **log_data)
        elif log_level == logging.WARNING:
            self.logger.warning(message, **log_data)
        elif log_level == logging.ERROR:
            self.logger.error(message, **log_data)
        elif log_level == logging.CRITICAL:
            self.logger.critical(message, **log_data)
