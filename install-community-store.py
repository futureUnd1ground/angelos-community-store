#!/usr/bin/env python3
"""Install or update AngelOS Community Store from its GitHub release."""
import argparse
import json
import os
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RELEASE_URL = "https://github.com/futureUnd1ground/angelos-community-store/releases/download/v0.9.1/community-store-v0.9.1.zip"
MAX_ARCHIVE = 64 * 1024 * 1024
TARGET = Path.home() / ".config/angelos/plugins/community-store"
LAUNCHER = Path.home() / ".local/bin/community-store"


def fail(message):
    raise RuntimeError(message)


def download(url, destination):
    if not url.startswith("https://"):
        fail("The release URL must use HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": "angelos-community-store-installer/1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        fail("The archive is larger than 64 MiB")
    destination.write_bytes(data)


def unpack_checked(archive, root):
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        if len(members) > 2000:
            fail("The archive contains too many files")
        if sum(item.file_size for item in members) > MAX_ARCHIVE:
            fail("The expanded archive is larger than 64 MiB")
        for item in members:
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                fail("The archive contains a symbolic link")
            target = (root / item.filename).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                fail("The archive contains an unsafe path")
        zf.extractall(root)
    manifests = list(root.glob("manifest.json")) + list(root.glob("*/manifest.json"))
    if len(manifests) != 1:
        fail("The archive must contain exactly one manifest.json")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("id") != "community-store":
        fail("The archive manifest is not community-store")
    if not str(manifest.get("version", "")).strip():
        fail("The archive manifest has no version")
    return manifest_path.parent, manifest


def install(url, restart=True):
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="community-store-install-", dir=TARGET.parent) as temp:
        temp_dir = Path(temp)
        archive = temp_dir / "store.zip"
        unpacked = temp_dir / "unpacked"
        unpacked.mkdir()
        print("Downloading Community Store...")
        download(url, archive)
        source, manifest = unpack_checked(archive, unpacked)
        staging = TARGET.parent / (".community-store.new-" + str(os.getpid()))
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source, staging)
        backup = None
        if TARGET.exists():
            backup = TARGET.parent / (".community-store.previous-" + str(os.getpid()))
            os.replace(TARGET, backup)
        try:
            os.replace(staging, TARGET)
        except Exception:
            if backup and backup.exists() and not TARGET.exists():
                os.replace(backup, TARGET)
            raise
        if backup and backup.exists():
            shutil.rmtree(backup)
    LAUNCHER.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHER.write_text("#!/bin/sh\nexec python3 \"$HOME/.config/angelos/plugins/community-store/scripts/community-store-tui.py\" \"$@\"\n")
    LAUNCHER.chmod(0o755)
    print("Installed Community Store {}".format(manifest["version"]))
    if restart and shutil.which("angelos"):
        subprocess.run(["angelos", "restart"], check=False)
        print("AngelOS restarted.")
    else:
        print("Run 'angelos restart' to load it, then run 'community-store'.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=RELEASE_URL, help="HTTPS release ZIP URL")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart AngelOS")
    args = parser.parse_args()
    try:
        install(args.url, restart=not args.no_restart)
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile, RuntimeError) as exc:
        print("Installation failed: {}".format(exc), file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
