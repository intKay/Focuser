"""Portable paths and an OS-owned single-writer lock, independent of desktop APIs."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

VERSION = '1.3.0rc2'
API_VERSION = 1


def default_data_dir(platform=None, env=None, home=None):
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)
    if platform == 'win32':
        return Path(env.get('LOCALAPPDATA', home / 'AppData/Local')) / 'Focuser'
    if platform == 'darwin':
        return home / 'Library/Application Support/Focuser'
    return Path(env.get('XDG_DATA_HOME', home / '.local/share')) / 'focuser'


def instance_id(data_dir):
    # Identity binds extension connections to a data directory without exposing it.
    path = os.path.normcase(str(Path(data_dir).expanduser().resolve()))
    return hashlib.sha256(path.encode()).hexdigest()[:32]


class DataLock:
    """Kernel lock: survives unlink-free restarts, releases after a crash."""
    def __init__(self, data_dir):
        self.path = Path(data_dir) / '.focuser.lock'
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0, 2)
                if handle.tell() == 0:
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise RuntimeError('该数据目录已由另一个 Focuser 服务使用，未启动第二个写入者') from None
        self.file = handle
        return self

    def close(self):
        if self.file is not None:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.close()
