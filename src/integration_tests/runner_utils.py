import contextlib
import os
import time

from termcolor import colored


@contextlib.contextmanager
def test_step(name: str):
    step = colored(f"[{name}]", "blue")
    print(step, "Starting")
    t0 = time.monotonic()
    try:
        yield
    except Exception as e:
        print(step, colored(f"Failed after {time.monotonic() - t0:.3f}s", "red"))
        raise e
    print(step, colored(f"Completed in {time.monotonic() - t0:.3f}s", "green"))


def integration_tests_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


def repo_root_dir() -> str:
    return os.path.dirname(os.path.dirname(integration_tests_dir()))
