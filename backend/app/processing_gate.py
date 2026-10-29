"""Serialize heavy jobs and preview generation on a single low-memory host."""
from contextlib import contextmanager
from functools import wraps
import fcntl
from pathlib import Path
from .config import settings

class ProcessingBusy(RuntimeError):
    pass

@contextmanager
def processing_slot(wait=True):
    if not settings().low_memory_mode:
        yield
        return
    root=Path(settings().storage_root)
    root.mkdir(parents=True,exist_ok=True)
    with (root/".heavy-processing.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            raise ProcessingBusy("A video is processing. Please retry the preview when it finishes.")
        try:
            yield
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)

def serial_processing(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with processing_slot():
            return function(*args,**kwargs)
    return wrapped
