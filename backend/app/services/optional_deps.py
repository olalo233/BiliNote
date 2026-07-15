"""Runtime installation of optional dependencies.

The default container deliberately omits the local faster-whisper stack.  This
module keeps that stack on the persistent data volume and adds it to the
current interpreter only when the local whisper engine is actually used.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

from app.utils.logger import get_logger

logger = get_logger(__name__)

LOCAL_WHISPER_REQUIREMENTS = (
    "faster-whisper==1.1.1",
    "ctranslate2==4.6.0",
    "av==14.2.0",
)

_INSTALL_LOCK = threading.Lock()


class LocalWhisperInstallError(RuntimeError):
    """Raised when the optional local whisper runtime cannot be installed."""


def runtime_deps_dir() -> Path:
    """Return the persistent, Python-version-specific optional dependency path."""

    data_dir = Path(os.getenv("DATA_DIR", "data")).expanduser()
    if not data_dir.is_absolute():
        data_dir = Path.cwd() / data_dir
    return data_dir / "runtime-deps" / f"py{sys.version_info.major}{sys.version_info.minor}"


def _prepare_import_path(create: bool = True) -> Path:
    target = runtime_deps_dir()
    if create:
        target.mkdir(parents=True, exist_ok=True)
    target_string = str(target)
    if target_string not in sys.path:
        sys.path.insert(0, target_string)
    importlib.invalidate_caches()
    return target


def _import_faster_whisper() -> ModuleType:
    _prepare_import_path(create=False)
    return importlib.import_module("faster_whisper")


def is_local_whisper_installed() -> bool:
    """Check availability without installing or downloading anything."""

    try:
        _import_faster_whisper()
    except Exception:
        return False
    return True


def _pip_environment() -> dict[str, str]:
    env = os.environ.copy()
    # Docker's supervisor default is intentionally empty so runtime settings
    # can supply PIP_INDEX_URL.  An empty value disables pip's normal default.
    if not env.get("PIP_INDEX_URL"):
        env.pop("PIP_INDEX_URL", None)
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _install_to(target: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--no-compile",
        "--upgrade",
        "--target",
        str(target),
        *LOCAL_WHISPER_REQUIREMENTS,
    ]
    logger.info(
        "local_whisper_install_started target=%s packages=%s",
        target,
        ",".join(LOCAL_WHISPER_REQUIREMENTS),
    )
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=_pip_environment(),
    )
    if completed.stdout:
        logger.info("local_whisper_install_stdout=%s", completed.stdout.strip())
    if completed.stderr:
        logger.info("local_whisper_install_stderr=%s", completed.stderr.strip())
    if completed.returncode != 0:
        raise LocalWhisperInstallError(
            "本地 Whisper 运行时安装失败，请检查容器网络与 PIP_INDEX_URL；"
            f"pip exit={completed.returncode}"
        )


def ensure_local_whisper() -> ModuleType:
    """Import local whisper, installing its pinned runtime into the data volume."""

    try:
        module = _import_faster_whisper()
        logger.info("local_whisper_runtime_ready source=%s", getattr(module, "__file__", "unknown"))
        return module
    except Exception:
        pass

    with _INSTALL_LOCK:
        # Another request may have finished the install while this request was
        # waiting for the lock.
        try:
            module = _import_faster_whisper()
            logger.info("local_whisper_runtime_ready source=%s", getattr(module, "__file__", "unknown"))
            return module
        except Exception:
            target = _prepare_import_path()
            _install_to(target)

        try:
            module = _import_faster_whisper()
        except Exception as exc:
            logger.exception("local_whisper_import_after_install_failed")
            raise LocalWhisperInstallError(
                "本地 Whisper 运行时已安装但导入失败，请删除 "
                f"{runtime_deps_dir()} 后重试："
                f"{exc}"
            ) from exc

        logger.info("local_whisper_runtime_installed target=%s", runtime_deps_dir())
        return module
