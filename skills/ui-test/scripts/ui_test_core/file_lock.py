"""Cross-process advisory ownership of one stable file."""
from __future__ import annotations

import errno
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class FileLockBusy(BlockingIOError):
    """Another process holds this advisory lock."""


@contextmanager
def exclusive_file_lock(lock_path: str | Path, *, blocking: bool = True,
                        existing_only: bool = False) -> Iterator[None]:
    path = Path(lock_path)
    if not existing_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("r+b" if existing_only else "a+b") as stream:
        stream.seek(0)  # Windows permits locking a byte beyond EOF.
        try:
            if os.name == "nt":
                import msvcrt

                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                msvcrt.locking(stream.fileno(), mode, 1)
            else:
                import fcntl

                mode = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
                fcntl.flock(stream.fileno(), mode)
        except OSError as exc:
            if not blocking and exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise FileLockBusy(str(path)) from exc
            raise
        try:
            yield
        finally:  # Entered only after successfully acquiring ownership.
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
