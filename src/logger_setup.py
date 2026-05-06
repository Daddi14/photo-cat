import ctypes
import logging
import os
import sys


def _enable_windows_ansi() -> bool:
    if (os.name != "nt"):
        return True

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()

        if (not kernel32.GetConsoleMode(handle, ctypes.byref(mode))):
            return False

        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _supports_color() -> bool:
    if (os.environ.get("NO_COLOR", "").strip()):
        return False

    if (not sys.stdout.isatty()):
        return False

    if (os.name == "nt"):
        return _enable_windows_ansi()

    return True


USE_COLOR = _supports_color()
COMPACT_LOG = (os.environ.get("PHOTO_CAT_COMPACT_LOG", "").strip() == "1")


class _CompactInfoFilter(logging.Filter):
    KEEP_PREFIXES = (
        "Loading catalog:",
        "Using ",
        "Loaded ",
        "Building cKDTree",
        "Building neighbor index",
        "Index saved to:",
        "Results saved to:",
        "Targets processed:",
        "Build step finished.",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if ((not COMPACT_LOG) or (record.levelno >= logging.WARNING)):
            return True

        if (record.levelno != logging.INFO):
            return True

        message = record.getMessage().strip()
        if (not message):
            return True

        if (set(message) <= {"=", "-"}):
            return False

        return message.startswith(self.KEEP_PREFIXES)


class _ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    DIM = "\033[90m"
    YELLOW = "\033[33m"
    RED = "\033[31m"

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if (message.startswith("ERROR:\n")):
            message = message[len("ERROR:\n"):]
        elif (message.startswith("ERROR: ")):
            message = message[len("ERROR: "):]
        elif (message == "ERROR:"):
            message = ""

        if (message.startswith("Results saved to: ") and USE_COLOR):
            save_prefix = "Results saved to: "
            save_path = message[len(save_prefix):]
            message = f"{save_prefix}{self.YELLOW}{save_path}{self.RESET}"

        output = message
        style = ""

        if (record.levelno >= logging.ERROR):
            output = f"[ERROR] {message}"
            style = self.RED
        elif (record.levelno >= logging.WARNING):
            output = f"[WARN]  {message}"
            style = self.YELLOW
        elif (record.levelno == logging.DEBUG):
            output = f"[DEBUG] {message}"
            style = self.DIM

        if ((not USE_COLOR) or (not style)):
            return output

        return f"{style}{output}{self.RESET}"


def get_logger(name: str):
    root = logging.getLogger()
    if (not root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(_ColorFormatter())
        handler.addFilter(_CompactInfoFilter())
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
