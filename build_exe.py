"""Stage, verify and package the Windows application before replacing the old build."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from core.version import APP_VERSION

ROOT = Path(__file__).resolve().parent


def build_environment(*, include_python=True):
    """Prevent unrelated PATH tools from supplying incompatible DLLs to the bundle."""
    environment = os.environ.copy()
    windows = Path(environment.get("SYSTEMROOT") or environment.get("WINDIR") or "C:/Windows")
    paths = [windows / "System32", windows, windows / "System32/Wbem"]
    if include_python:
        paths = [Path(sys.base_prefix), Path(sys.executable).parent, *paths]
    environment["PATH"] = os.pathsep.join(str(path) for path in paths)
    for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        environment.pop(name, None)
    return environment


def checked_path(path: Path, workspace: Path = ROOT) -> Path:
    resolved, root = path.resolve(), workspace.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(f"Build target is outside the intended workspace: {resolved}")
    return resolved


def promote_build(staged: Path, target: Path, backup: Path, workspace: Path = ROOT):
    """Retain the old directory, and restore it if promotion fails."""
    staged, target, backup = (checked_path(p, workspace) for p in (staged, target, backup))
    paths = (staged, target, backup)
    for index, path in enumerate(paths):
        for other in paths[index + 1:]:
            if path.is_relative_to(other) or other.is_relative_to(path):
                raise ValueError("Build, installation and backup paths must be separate directories")
    if not (staged / "Reelsator.exe").is_file():
        raise FileNotFoundError("Verified staged executable is missing")
    if backup.exists():
        raise FileExistsError(f"Backup already exists: {backup}")
    target.parent.mkdir(parents=True, exist_ok=True)
    had_previous = target.exists()
    if had_previous:
        backup.parent.mkdir(parents=True, exist_ok=True)
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except OSError:
        if had_previous:
            os.replace(backup, target)
        raise
    return backup if had_previous else None


def unique_archive_path(dist: Path) -> Path:
    name = f"Reelsator-v{APP_VERSION}-windows-x64"
    candidate, index = dist / f"{name}.zip", 2
    while candidate.exists():
        candidate = dist / f"{name}-{index}.zip"
        index += 1
    return candidate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build():
    build_root = checked_path(ROOT / "build")
    dist_root = checked_path(ROOT / "dist")
    build_root.mkdir(parents=True, exist_ok=True)
    dist_root.mkdir(parents=True, exist_ok=True)
    staging = checked_path(Path(tempfile.mkdtemp(prefix="package-", dir=build_root)))
    staged_dist = staging / "dist" / "Reelsator"
    print(f"Building Reelsator {APP_VERSION} in {staging}", flush=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        "--distpath", str(staging / "dist"), "--workpath", str(staging / "work"),
        str(ROOT / "Reelsator.spec"),
    ], cwd=ROOT, check=True, env=build_environment())

    executable = staged_dist / "Reelsator.exe"
    shutil.copyfile(ROOT / "assets/icon.ico", staged_dist / "icon.ico")
    smoke_report = staged_dist / "smoke-test-report.json"
    print("Checking the actual packaged executable...", flush=True)
    # The windowed executable has no console: its JSON report is the verification result.
    smoke = subprocess.run([
        str(executable), "--smoke-test", "--smoke-test-report", str(smoke_report),
    ], cwd=staging, timeout=120, env=build_environment(include_python=False))
    report = json.loads(smoke_report.read_text(encoding="utf-8")) if smoke_report.exists() else {}
    if (smoke.returncode != 0 or report.get("status") != "passed"
            or report.get("version") != APP_VERSION or report.get("frozen") is not True):
        raise RuntimeError(f"Packaged smoke test failed. Old build kept. Details: {smoke_report}; {report}")

    (staged_dist / "README.txt").write_text(
        f"Reelsator {APP_VERSION}\n\n"
        "Запустите Reelsator.exe. Python устанавливать не требуется.\n"
        "Переносите всю папку Reelsator вместе с подпапкой _internal.\n\n"
        "Soft Flash: мягкий цвет и мелкое зерно.\n"
        "Digicam Flash: ярче, контрастнее, с цветным зерном.\n"
        "Личные настройки: «Мои пресеты» → «Сохранить как…».\n"
        "Пресеты хранятся в %APPDATA%\\Reelsator\\presets.json и сохраняются после обновления.\n"
        "Результат проверяйте в режиме «100% / После JPEG».\n",
        encoding="utf-8-sig",
    )
    archive_path = unique_archive_path(dist_root)
    temporary_archive = staging / "package.zip"
    print("Creating the portable ZIP...", flush=True)
    with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(staged_dist.rglob("*")):
            if path.is_file():
                archive.write(path, Path("Reelsator") / path.relative_to(staged_dist))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = dist_root / "backups" / f"Reelsator-{stamp}-{uuid.uuid4().hex[:8]}"
    previous = promote_build(staged_dist, dist_root / "Reelsator", backup_path)
    os.replace(temporary_archive, archive_path)
    installed_exe = dist_root / "Reelsator/Reelsator.exe"
    build_report = {
        "version": APP_VERSION, "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "executable": str(installed_exe), "executable_sha256": sha256(installed_exe),
        "archive": str(archive_path), "archive_sha256": sha256(archive_path),
        "previous_build": str(previous) if previous else None, "smoke_test": report,
    }
    archive_path.with_suffix(".build.json").write_text(
        json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Build passed: {installed_exe}\nPortable ZIP: {archive_path}\nPrevious build: {previous}", flush=True)


if __name__ == "__main__":
    build()
