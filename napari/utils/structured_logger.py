"""Structured logger for debugging."""

import structlog


def setup_structured_logger(json_logs: bool = False, log_level: str = 'DEBUG'):
    """Initialize the structured logger."""
    if json_logs:
        log_renderer = structlog.processors.JSONRenderer()
    else:
        log_renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(
                fmt='%Y-%m-%d %H:%M:%S', utc=False
            ),
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.PROCESS,
                    structlog.processors.CallsiteParameter.THREAD,
                }
            ),
            log_renderer,
        ],
        # set the logging level to display in the console. NOTSET is all levels.
        wrapper_class=structlog.make_filtering_bound_logger(log_level.upper()),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    return structlog.get_logger()
