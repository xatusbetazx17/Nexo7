"""Build on the target operating system using PyInstaller, then create a portable archive."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.13.0"


def main():
    windows = sys.platform == "win32"
    if sys.platform not in {"linux", "win32"}:
        raise SystemExit("This release packages Windows and Linux only")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
               "--name", "Nexo7", "--collect-data", "nexo7", "--exclude-module", "torch",
               "--exclude-module", "tkinter", "--exclude-module", "pytest", "desktop_entry.py"]
    if windows:
        command.insert(-1, "--windowed")
    subprocess.run(command, cwd=ROOT, check=True)
    binary = ROOT / "dist" / ("Nexo7.exe" if windows else "Nexo7")
    subprocess.run([sys.executable, "scripts/smoke_desktop.py", str(binary)], cwd=ROOT, check=True)
    system = "windows" if windows else "linux"
    machine = platform.machine().lower()
    arch = "x86_64" if machine in {"amd64", "x86_64"} else machine
    name = f"Nexo7-{VERSION}-{system}-{arch}"
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    stage = ROOT / "build" / name
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, stage / binary.name)
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE.txt")
    shutil.copy2(ROOT / "docs" / "COMPANION.md", stage / "COMPANION.md")
    shutil.copy2(ROOT / "docs" / "TASK-AGENT.md", stage / "TASK-AGENT.md")
    shutil.copy2(ROOT / "docs" / "CONTRIBUTIONS.md", stage / "CONTRIBUTIONS.md")
    shutil.copy2(ROOT / "THIRD-PARTY.md", stage / "THIRD-PARTY.md")
    shutil.copy2(ROOT / "docs" / "CREATIVE-STUDIO.md", stage / "CREATIVE-STUDIO.md")
    licenses = stage / "licenses"
    licenses.mkdir(exist_ok=True)
    for source in (ROOT / "nexo7" / "licenses").glob("*.txt"):
        shutil.copy2(source, licenses / source.name)
    shutil.copy2(ROOT / "docs" / "VISION-TELEGRAM.md", stage / "VISION-TELEGRAM.md")
    from importlib.metadata import distribution
    package = distribution("pyinstaller")
    for entry in package.files or []:
        if str(entry).endswith("licenses/COPYING.txt"):
            shutil.copy2(package.locate_file(entry), licenses / "PYINSTALLER-COPYING.txt")
    for entry in distribution("pypdf").files or []:
        if str(entry).endswith("licenses/LICENSE"):
            shutil.copy2(distribution("pypdf").locate_file(entry), licenses / "PYPDF-LICENSE.txt")
    for entry in distribution("Pillow").files or []:
        if "licenses/" in str(entry) and str(entry).endswith(("LICENSE", "LICENSE.txt")):
            shutil.copy2(distribution("Pillow").locate_file(entry), licenses / ("PILLOW-" + Path(str(entry)).name))
    for candidate in (Path(sysconfig.get_path("stdlib")) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE.txt"):
        if candidate.exists():
            shutil.copy2(candidate, licenses / "PYTHON-LICENSE.txt")
            break
    shutil.copy2(ROOT / "docs" / "QUICKSTART.md", stage / "START-HERE.md")
    shutil.copy2(ROOT / "docs" / "LEARNING.md", stage / "LEARNING.md")
    shutil.copy2(ROOT / "docs" / "WEB-RESEARCH.md", stage / "WEB-RESEARCH.md")
    if windows:
        archive = output / (name + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as file:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    file.write(path, path.relative_to(stage.parent))
    else:
        archive = output / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as file:
            file.add(stage, arcname=name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + ".sha256")).write_text(digest + "  " + archive.name + "\n")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size,
                      "sha256": digest, "platform": platform.platform()}, indent=2))


if __name__ == "__main__":
    main()
