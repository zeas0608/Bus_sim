"""Install two pinned CPython 3.11/Win64 wheels without invoking pip.

UE 5.5's bundled python.exe must not be modified. Only Saved/TakamatsuStage1
is written. Downloads are from PyPI's official file host, and the exact
sha256 hashes from requirements-win64.txt are verified *before* extraction.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

# Official PyPI files for cp311-cp311-win_amd64, not arbitrary latest packages.
WHEELS = {
    "numpy": (
        "1.26.4",
        "https://files.pythonhosted.org/packages/3f/6b/"
        "5610004206cf7f8e7ad91c5a85a8c71b2f2f8051a0c0c4d5916b76d6cbb2/"
        "numpy-1.26.4-cp311-cp311-win_amd64.whl",
    ),
    "shapely": (
        "2.1.2",
        "https://files.pythonhosted.org/packages/38/1e/"
        "3f8ea46353c2a33c1669eb7327f9665103aa3a8dfe7f2e4ef714c210b2c2/"
        "shapely-2.1.2-cp311-cp311-win_amd64.whl",
    ),
}
MAX_WHEEL_BYTES = 45 * 1024 * 1024
MAX_EXTRACT_BYTES = 180 * 1024 * 1024


def locked_hashes(requirements: Path) -> dict[str, tuple[str, str]]:
    pins: dict[str, tuple[str, str]] = {}
    for line in requirements.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9_-]+)==([0-9.]+)\s+--hash=sha256:([a-f0-9]{64})", line
        )
        if not match:
            raise ValueError("Invalid pinned requirement (only exact hashes allowed): " + line)
        name, version, digest = match.groups()
        if name in pins:
            raise ValueError("Duplicate pinned package: " + name)
        pins[name] = (version, digest)
    if pins.keys() != WHEELS.keys():
        raise ValueError("Pinned requirements must include exactly numpy and shapely")
    return pins


def download_verified(url: str, destination: Path, expected: str) -> None:
    if destination.is_file():
        if hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
            print("Verified cached wheel:", destination.name, flush=True)
            return
        raise ValueError("Cached wheel has a SHA-256 mismatch; refusing unsafe reuse: " + str(destination))

    tmp = destination.with_name(destination.name + ".part")
    h = hashlib.sha256()
    total = 0
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "KotodenBusSimulator-Stage1/1.1 (Python wheel bootstrap)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, tmp.open("xb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_WHEEL_BYTES:
                    raise ValueError("Wheel download exceeds size limit: " + destination.name)
                output.write(chunk)
                h.update(chunk)
        if h.hexdigest() != expected:
            raise ValueError("Official wheel SHA-256 mismatch: " + destination.name)
        tmp.replace(destination)
        print("Downloaded and SHA-256 verified:", destination.name, flush=True)
    finally:
        tmp.unlink(missing_ok=True)


def unpack_safe(wheel: Path, dest: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        if sum(info.file_size for info in members) > MAX_EXTRACT_BYTES:
            raise ValueError("Wheel uncompressed size exceeds limit: " + wheel.name)
        for info in members:
            p = PurePosixPath(info.filename)
            if (p.is_absolute() or ".." in p.parts or
                    info.filename.startswith(("/", "\\")) or
                    "\\" in info.filename or ":" in info.filename):
                raise ValueError("Wheel contains unsafe path: " + info.filename)
            if not p.parts:
                continue
            # These pinned wheels contain normal module trees and dist-info;
            # they require no scripts and must not install into Unreal Engine.
            if info.is_dir():
                (dest.joinpath(*p.parts)).mkdir(parents=True, exist_ok=True)
            else:
                out = dest.joinpath(*p.parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as inp, out.open("wb") as output:
                    shutil.copyfileobj(inp, output)


def install(dest: Path, cache: Path, requirements: Path) -> None:
    if sys.version_info[:2] != (3, 11) or os.name != "nt" or sys.maxsize <= 2**32:
        raise RuntimeError("This installer requires UE Python 3.11 64-bit on Windows.")
    pins = locked_hashes(requirements)
    cache.mkdir(parents=True, exist_ok=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError("Refusing to overwrite existing dependencies: " + str(dest))
    stage = Path(tempfile.mkdtemp(prefix="Stage1-wheel-", dir=dest.parent))
    try:
        for name, (version, url) in WHEELS.items():
            pinned_version, digest = pins[name]
            if pinned_version != version:
                raise ValueError(f"Locked version of {name} does not match bootstrapped version")
            filename = url.rsplit("/", 1)[-1]
            if filename != f"{name}-{version}-cp311-cp311-win_amd64.whl":
                raise ValueError("Unexpected wheel compatibility tag: " + filename)
            wheel = cache / filename
            download_verified(url, wheel, digest)
            unpack_safe(wheel, stage)
        # Publishing a finished tree in one rename prevents partial reused installs.
        stage.rename(dest)
        print("Verified pinned Windows wheel dependencies installed into", dest, flush=True)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: bootstrap_wheels.py <new target directory> <wheel-cache-dir>", file=sys.stderr)
        return 2
    dest, cache = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    try:
        install(dest, cache, Path(__file__).with_name("requirements-win64.txt"))
    except Exception as exc:
        print("STAGE1 DEPENDENCY ERROR: " + str(exc), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
