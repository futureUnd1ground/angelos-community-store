#!/usr/bin/env python3
"""Small, dependency-free registry and installer for Community Store."""
import fcntl, json, os, shutil, sys, tempfile, time, urllib.error, urllib.parse, urllib.request, uuid, zipfile
from pathlib import Path

MAX_REGISTRY = 2 * 1024 * 1024
MAX_ARCHIVE = 64 * 1024 * 1024
ID = __import__('re').compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")

def fail(message):
    print(message, file=sys.stderr)
    return 1

def fetch(url):
    if not url.startswith("https://"):
        return fail("Registry URL must use HTTPS")
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("_angelos_store", str(time.time_ns())))
    url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    request = urllib.request.Request(url, headers={"User-Agent": "angelos-community-store/0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(MAX_REGISTRY + 1)
    if len(data) > MAX_REGISTRY:
        return fail("Registry is too large")
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("plugins"), list):
        return fail("Unsupported registry format")
    seen = set()
    for entry in payload["plugins"]:
        if not isinstance(entry, dict):
            return fail("Registry contains an invalid plugin entry")
        plugin_id = entry.get("id")
        if not isinstance(plugin_id, str) or not ID.fullmatch(plugin_id) or plugin_id in seen:
            return fail("Registry contains an invalid or duplicate plugin id")
        seen.add(plugin_id)
        for field in ("name", "version", "source"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                return fail("Registry plugin " + plugin_id + " has an invalid " + field)
        if not entry["source"].startswith("https://"):
            return fail("Registry contains a non-HTTPS source")
        for field in ("author", "description", "category", "repository", "homepage", "icon", "status"):
            if field in entry and not isinstance(entry[field], str):
                return fail("Registry plugin " + plugin_id + " has an invalid " + field)
        for field in ("tags", "dependencies", "permissions"):
            if field in entry and (not isinstance(entry[field], list) or not all(isinstance(value, str) for value in entry[field])):
                return fail("Registry plugin " + plugin_id + " has an invalid " + field)
    print(json.dumps(payload, ensure_ascii=False))
    return 0

def install(source, expected_id, expected_version):
    if not ID.fullmatch(expected_id) or not source.startswith("https://"):
        return fail("Invalid plugin id or source")
    parent = Path.home() / ".config/angelos/plugins"
    parent.mkdir(parents=True, exist_ok=True)
    # Serialize GUI, launcher and TUI installs of the same plugin.
    with (parent / ("." + expected_id + ".install.lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return fail("Another installation of " + expected_id + " is running")
        return install_locked(source, expected_id, expected_version)


def install_locked(source, expected_id, expected_version):
    request = urllib.request.Request(source, headers={"User-Agent": "angelos-community-store/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        return fail("Plugin archive is too large")
    home = Path.home()
    destination = home / ".config/angelos/plugins" / expected_id
    trash = home / ".local/state/angelos/plugin-trash"
    if destination.is_symlink():
        return fail("Refusing to replace a symbolic-link plugin directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".community-store-", dir=destination.parent) as work:
        archive = Path(work) / "plugin.zip"
        archive.write_bytes(data)
        root = Path(work) / "unpacked"
        root.mkdir()
        with zipfile.ZipFile(archive) as zf:
            if len(zf.infolist()) > 2000 or sum(item.file_size for item in zf.infolist()) > MAX_ARCHIVE:
                return fail("Plugin archive expands beyond allowed limits")
            for member in zf.infolist():
                mode = member.external_attr >> 16
                if __import__('stat').S_ISLNK(mode):
                    return fail("Archive contains a symbolic link")
                target = (root / member.filename).resolve()
                if not str(target).startswith(str(root.resolve()) + os.sep):
                    return fail("Archive contains an unsafe path")
            zf.extractall(root)
            for member in zf.infolist():
                target = root / member.filename
                if target.is_file():
                    target.chmod(target.stat().st_mode | ((member.external_attr >> 16) & 0o111))
        manifests = list(root.glob("manifest.json")) + list(root.glob("*/manifest.json"))
        if len(manifests) != 1:
            return fail("Archive must contain one manifest.json")
        source_dir = manifests[0].parent
        try:
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return fail("Invalid manifest: " + str(exc))
        if not isinstance(manifest, dict) or manifest.get("id") != expected_id or not ID.fullmatch(expected_id):
            return fail("Manifest id does not match registry")
        if str(manifest.get("version", "")) != expected_version:
            return fail("Manifest version does not match registry")
        if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
            return fail("Manifest name is required")
        staging = Path(work) / "staged"
        shutil.copytree(source_dir, staging)
        backup = None
        try:
            if destination.exists():
                # Rollback must stay on the same filesystem as the plugin.
                backup = destination.parent / ("." + expected_id + ".previous-" + uuid.uuid4().hex)
                os.replace(destination, backup)
            os.replace(staging, destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup is not None:
            try:
                trash.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup), str(trash / backup.name.lstrip(".")))
            except OSError:
                # The installation succeeded; retain the backup if trash is unavailable.
                print("Previous plugin retained at " + str(backup), file=sys.stderr)
    print("Installed " + expected_id + " " + expected_version)
    return 0

def main(args=None):
    args = sys.argv[1:] if args is None else args
    try:
        if len(args) == 2 and args[0] == "fetch":
            return fetch(args[1])
        if len(args) == 4 and args[0] == "install":
            return install(args[1], args[2], args[3])
        return fail("Usage: community-store.py fetch URL | install SOURCE ID VERSION")
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile, RuntimeError) as exc:
        return fail("Community Store: " + str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
