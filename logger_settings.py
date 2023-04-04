import logging
import sys

# Define log formatting with colors
logging_format = "%(asctime)s | %(name)s | %(levelname)s | \033[%(color_code)sm%(message)s\033[0m"

# Define color codes for different log levels
logging.addLevelName(logging.DEBUG, "DEBUG")
logging.addLevelName(logging.INFO, "INFO")
logging.addLevelName(logging.WARNING, "WARNING")
logging.addLevelName(logging.ERROR, "ERROR")
logging.addLevelName(logging.CRITICAL, "CRITICAL")

COLORS = {
    "DEBUG": "36",
    "INFO": "32",
    "WARNING": "33",
    "ERROR": "31",
    "CRITICAL": "41;30",
}


# Define a custom formatter that adds color codes to the logging messages
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        record.color_code = COLORS.get(record.levelname, "0")
        return super().format(record)


# Create a logger and set its level to DEBUG
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a console handler and set its level to DEBUG
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

# Set the formatter for the console handler
formatter = ColoredFormatter(logging_format, datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)

# Add the console handler to the logger
logger.addHandler(console_handler)
