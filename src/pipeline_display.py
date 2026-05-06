import ctypes
import os
import re
import shutil
import sys
import threading
import time


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[90m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"


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


def color(text: str, style: str) -> str:
    if (not USE_COLOR):
        return text

    return f"{style}{text}{Style.RESET}"


def write_progress_suffix(suffix: str) -> None:
    if (not suffix):
        return

    match = re.match(r"^(?:(?P<spinner>[-\\|/])\s+)?(?P<count>\d+/\d+)(?P<rest>\s+\[.*\])$", suffix)
    if (match):
        spinner = match.group("spinner")
        count = match.group("count")
        rest = match.group("rest")

        if (spinner):
            sys.stdout.write(color(f"  {spinner}", Style.GRAY))
            sys.stdout.write(f"  {count}")
        else:
            sys.stdout.write(f"  {count}")

        sys.stdout.write(color(rest, Style.GRAY))
        return

    sys.stdout.write(color(f"  {suffix}", Style.GRAY))


def progress_bar(percent: int, detail: str = "", spinner: str = "", complete: bool = False, width: int = 34) -> None:
    percent = max(0, min(int(percent), 100))

    terminal_width = shutil.get_terminal_size((88, 20)).columns
    max_width = max(42, min(terminal_width - 1, 96))

    prefix = "    "
    percent_text = f"{percent:3d}%"

    suffix_parts = []
    if (spinner):
        suffix_parts.append(str(spinner))
    if (detail):
        suffix_parts.append(str(detail))
    suffix = "  ".join(suffix_parts)

    min_bar_width = 10
    max_bar_width = min(width, 34)
    reserved = len(prefix) + len(percent_text) + 4

    max_suffix_len = max(0, max_width - reserved - min_bar_width - 2)
    if (len(suffix) > max_suffix_len):
        suffix = suffix[:max(0, max_suffix_len - 1)] + "." if (max_suffix_len > 1) else ""

    bar_width = max_width - reserved - len(suffix)
    if (suffix):
        bar_width -= 2
    bar_width = max(min_bar_width, min(max_bar_width, bar_width))

    filled = int(round(bar_width * (percent / 100.0)))
    empty = bar_width - filled

    filled_part = "=" * filled
    empty_part = "-" * empty

    if (USE_COLOR):
        sys.stdout.write("\r\033[2K")
    else:
        sys.stdout.write("\r" + (" " * max_width) + "\r")

    sys.stdout.write(prefix)
    if (filled_part):
        sys.stdout.write(color(filled_part, Style.MAGENTA))
    if (empty_part):
        sys.stdout.write(color(empty_part, Style.GRAY))
    sys.stdout.write("  ")
    sys.stdout.write(color(percent_text, Style.GREEN))
    if (suffix):
        write_progress_suffix(suffix)
    sys.stdout.flush()

    if (complete):
        sys.stdout.write("\n")
        sys.stdout.flush()


class ActivityBar:
    def __init__(self, detail: str, start: int = 2, stop: int = 94, interval: float = 0.12):
        self.detail = detail
        self.start = start
        self.stop = stop
        self.interval = interval
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._done.set()
        self._thread.join(timeout=1.0)
        progress_bar(100, self.detail, complete=True)
        return False

    def _run(self) -> None:
        percent = self.start
        direction = 1
        while (not self._done.is_set()):
            progress_bar(percent, self.detail, complete=False)
            percent += direction
            if (percent >= self.stop):
                percent = self.stop
                direction = -1
            elif (percent <= self.start):
                percent = self.start
                direction = 1
            self._done.wait(self.interval)


def tqdm_options(desc: str, total_width: int = 88) -> dict:
    return {
        "desc": desc,
        "ncols": None,
        "bar_format": "{desc}: {percentage:3.0f}%|{bar:24}| {n_fmt}/{total_fmt}",
        "dynamic_ncols": True,
        "leave": True,
    }
