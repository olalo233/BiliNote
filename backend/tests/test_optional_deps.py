import sys
from types import ModuleType

from app.services import optional_deps


def test_runtime_deps_dir_uses_data_volume_and_python_version(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    path = optional_deps.runtime_deps_dir()

    assert path == tmp_path / "data" / "runtime-deps" / f"py{sys.version_info.major}{sys.version_info.minor}"


def test_ensure_local_whisper_installs_once_then_imports(tmp_path, monkeypatch):
    target = tmp_path / "runtime-deps" / f"py{sys.version_info.major}{sys.version_info.minor}"
    module = ModuleType("faster_whisper")
    imports = iter([
        ModuleNotFoundError("faster_whisper"),
        ModuleNotFoundError("faster_whisper"),
        module,
    ])
    install_targets = []

    def import_side_effect():
        result = next(imports)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(optional_deps, "runtime_deps_dir", lambda: target)
    monkeypatch.setattr(optional_deps, "_import_faster_whisper", import_side_effect)
    monkeypatch.setattr(optional_deps, "_install_to", install_targets.append)

    assert optional_deps.ensure_local_whisper() is module
    assert install_targets == [target]


def test_default_requirements_do_not_include_optional_whisper_stack():
    assert optional_deps.LOCAL_WHISPER_REQUIREMENTS == (
        "faster-whisper==1.1.1",
        "ctranslate2==4.6.0",
        "av==14.2.0",
    )
