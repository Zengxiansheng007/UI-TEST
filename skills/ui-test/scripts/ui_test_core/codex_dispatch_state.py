"""Local task journal. All changes are short transactions under the task's stable lock."""
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .file_lock import exclusive_file_lock


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def publish(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def transaction(task):
    task = Path(task)
    with exclusive_file_lock(task.with_suffix(task.suffix + ".lock")):
        state = read(task) if task.exists() else {"version": 1, "active": None, "batches": {}}
        yield state
        publish(task, state)
