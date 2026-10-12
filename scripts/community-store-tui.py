#!/usr/bin/env python3
"""Terminal interface for the AngelOS Community Store."""
import curses
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
DEFAULT_REGISTRY = "https://raw.githubusercontent.com/futureUnd1ground/angelos-community-registry/main/plugins.json"
HELPER = HERE / "community-store.py"
HOME = Path.home()
PLUGIN_DIR = HOME / ".config/angelos/plugins"
TRASH_DIR = HOME / ".local/state/angelos/plugin-trash"
LAUNCHER = HOME / ".local/bin/community-store"


def ensure_launcher():
    LAUNCHER.parent.mkdir(parents=True, exist_ok=True)
    body = "#!/bin/sh\nexec python3 \"$HOME/.config/angelos/plugins/community-store/scripts/community-store-tui.py\" \"$@\"\n"
    if not LAUNCHER.exists() or LAUNCHER.read_text(errors="replace") != body:
        LAUNCHER.write_text(body)
        LAUNCHER.chmod(0o755)


def display_text(value, default):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for candidate in [value.get("en"), value.get("ru"), *value.values()]:
            if isinstance(candidate, str) and candidate:
                return candidate
    return default


def installed_plugins():
    found = {}
    if not PLUGIN_DIR.is_dir():
        return found
    for folder in PLUGIN_DIR.iterdir():
        manifest_path = folder / "manifest.json"
        if folder.name.startswith(".") or folder.is_symlink() or not folder.is_dir() or not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                continue
            plugin_id = manifest.get("id", folder.name)
            if isinstance(plugin_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", plugin_id) and plugin_id == folder.name:
                manifest["_path"] = folder
                manifest["name"] = display_text(manifest.get("name"), plugin_id)
                manifest["description"] = display_text(manifest.get("description"), "")
                manifest["author"] = display_text(manifest.get("author"), "Unknown")
                found[plugin_id] = manifest
        except (OSError, ValueError):
            continue
    return found


def registry_url():
    settings_path = HOME / ".config/angelos/settings.json"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        value = data.get("plugins", {}).get("data", {}).get("community-store", {}).get("registryUrl", DEFAULT_REGISTRY)
        return value if isinstance(value, str) and value.startswith("https://") else DEFAULT_REGISTRY
    except (OSError, ValueError, AttributeError):
        return DEFAULT_REGISTRY


def fetch_registry():
    url = registry_url()
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("_angelos_store", str(time.time_ns())))
    url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    result = subprocess.run([sys.executable, str(HELPER), "fetch", url], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not load registry")
    payload = json.loads(result.stdout)
    return [p for p in payload["plugins"] if p.get("status") == "approved"]


def version_tuple(value):
    try:
        parts = [int(part) for part in str(value).split(".")]
        while len(parts) > 1 and parts[-1] == 0:
            parts.pop()
        return tuple(parts)
    except ValueError:
        return (0,)


def is_update(installed, entry):
    return bool(installed and version_tuple(entry.get("version", "0")) > version_tuple(installed.get("version", "0")))


def plugin_rows(entries):
    installed = installed_plugins()
    by_id = {entry["id"]: entry for entry in entries}
    rows = []
    for entry in entries:
        local = installed.get(entry["id"])
        state = "UPDATE" if is_update(local, entry) else "INSTALLED" if local else "AVAILABLE"
        rows.append({"entry": entry, "installed": local, "state": state})
    for plugin_id, local in installed.items():
        if plugin_id not in by_id:
            rows.append({"entry": {
                "id": plugin_id,
                "name": local.get("name", plugin_id),
                "author": local.get("author", "Unknown"),
                "version": local.get("version", "0"),
                "description": local.get("description", "Installed local plugin"),
                "tags": [],
                "repository": "",
                "source": "",
            }, "installed": local, "state": "LOCAL"})
    return sorted(rows, key=lambda row: (row["entry"].get("name", "").lower(), row["entry"]["id"]))


def install(row):
    entry = row["entry"]
    result = subprocess.run([sys.executable, str(HELPER), "install", entry.get("source", ""), entry["id"], str(entry.get("version", ""))], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Install failed")
    return result.stdout.strip()


def remove(row):
    plugin_id = row["entry"]["id"]
    if plugin_id == "community-store":
        raise RuntimeError("Community Store cannot remove itself")
    if not isinstance(plugin_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", plugin_id):
        raise RuntimeError("Invalid plugin id")
    folder = PLUGIN_DIR / plugin_id
    if folder.is_symlink():
        raise RuntimeError("Symbolic-link plugin directories cannot be removed here")
    local = row.get("installed")
    if not local or not folder.is_dir():
        raise RuntimeError("Only user-installed plugins can be removed here")
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = TRASH_DIR / (stamp + "-" + plugin_id + "-" + uuid.uuid4().hex)
    shutil.move(str(folder), str(target))
    return "Moved to AngelOS plugin trash: " + target.name


class StoreUI:
    def __init__(self, screen):
        self.screen = screen
        self.entries = []
        self.rows = []
        self.selected = 0
        self.query = ""
        self.view = "ALL"
        self.message = "Loading registry..."
        self.error = False
        self.dirty = False
        self.running = True
        self.refresh()

    def refresh(self):
        try:
            self.entries = fetch_registry()
            self.error = False
            self.message = "Registry refreshed."
        except Exception as exc:
            self.error = True
            self.message = str(exc)
        self.rebuild()

    def rebuild(self):
        rows = plugin_rows(self.entries)
        if self.view == "INSTALLED":
            rows = [row for row in rows if row["installed"]]
        elif self.view == "UPDATES":
            rows = [row for row in rows if row["state"] == "UPDATE"]
        query = self.query.casefold().strip()
        if query:
            rows = [row for row in rows if query in " ".join([
                row["entry"].get("name", ""), row["entry"].get("id", ""),
                row["entry"].get("author", ""), row["entry"].get("description", ""),
                " ".join(row["entry"].get("tags", [])),
            ]).casefold()]
        self.rows = rows
        self.selected = min(self.selected, max(0, len(rows) - 1))

    def draw(self):
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height < 12 or width < 50:
            self.screen.addnstr(0, 0, "Resize terminal to at least 50x12", max(1, width - 1))
            self.screen.refresh()
            return
        title = " ANGEL OS COMMUNITY STORE "
        self.screen.addnstr(0, 0, title.ljust(width - 1), width - 1, curses.color_pair(1) | curses.A_BOLD)
        tabs = " [A]ll   [I]nstalled   [V] Updates "
        self.screen.addnstr(1, 0, tabs.ljust(width - 1), width - 1, curses.A_BOLD)
        query = "Search: " + (self.query or "(press / to search)")
        self.screen.addnstr(2, 0, query.ljust(width - 1), width - 1, curses.color_pair(2))
        list_bottom = max(5, height - 8)
        visible_count = list_bottom - 4
        start = max(0, min(self.selected - visible_count + 1, len(self.rows) - visible_count))
        start = max(0, start)
        for index, row in enumerate(self.rows[start:start + visible_count], start):
            entry = row["entry"]
            state = row["state"]
            version = entry.get("version", "?")
            installed = row.get("installed")
            if installed:
                version = str(installed.get("version", "?")) + (" -> " + version if state == "UPDATE" else "")
            label = "{:9} {:24.24} {:14.14} v{}".format(state, entry.get("name", entry["id"]), entry.get("author", ""), version)
            attr = curses.A_REVERSE if index == self.selected else curses.A_NORMAL
            self.screen.addnstr(4 + index - start, 0, label.ljust(width - 1), width - 1, attr)
        if not self.rows:
            self.screen.addnstr(4, 0, "No plugins match this view.".ljust(width - 1), width - 1)
        divider = min(height - 7, list_bottom + 1)
        self.screen.addnstr(divider, 0, "-" * (width - 1), width - 1, curses.color_pair(2))
        detail_y = divider + 1
        if self.rows and detail_y < height - 3:
            entry = self.rows[self.selected]["entry"]
            state = self.rows[self.selected]["state"]
            self.screen.addnstr(detail_y, 0, (entry.get("name", "") + "  [" + state + "]").ljust(width - 1), width - 1, curses.A_BOLD)
            desc = entry.get("description", "").replace("\n", " ")
            self.screen.addnstr(detail_y + 1, 0, desc.ljust(width - 1), width - 1)
            meta = "Tags: " + ", ".join(entry.get("tags", [])) + "  Repository: " + entry.get("repository", "")
            self.screen.addnstr(detail_y + 2, 0, meta.ljust(width - 1), width - 1, curses.color_pair(2))
        msg_attr = curses.color_pair(3) if self.error else curses.color_pair(2)
        self.screen.addnstr(height - 2, 0, self.message.ljust(width - 1), width - 1, msg_attr)
        footer = "Enter install/update  d remove  U update all  s update Store  r refresh  / search  q quit"
        self.screen.addnstr(height - 1, 0, footer.ljust(width - 1), width - 1, curses.A_DIM)
        self.screen.refresh()

    def prompt(self, label):
        height, width = self.screen.getmaxyx()
        curses.echo()
        curses.curs_set(1)
        self.screen.move(height - 2, 0)
        self.screen.clrtoeol()
        self.screen.addnstr(height - 2, 0, label, width - 1)
        value = self.screen.getstr(height - 2, min(len(label), width - 2), max(1, width - len(label) - 2)).decode(errors="replace")
        curses.noecho()
        curses.curs_set(0)
        return value

    def selected_row(self):
        return self.rows[self.selected] if self.rows else None

    def action_install(self, row=None):
        row = row or self.selected_row()
        if not row:
            return
        if not row["entry"].get("source"):
            self.message = "This local plugin has no registry release."
            self.error = True
            return
        if row["state"] in ("INSTALLED", "LOCAL"):
            self.message = "Plugin is already installed."
            return
        self.message = "Installing " + row["entry"]["id"] + "..."
        self.draw()
        try:
            self.message = install(row)
            self.error = False
            self.dirty = True
            self.refresh_after_action()
        except Exception as exc:
            self.message = str(exc)
            self.error = True

    def refresh_after_action(self):
        self.rebuild()

    def action_remove(self):
        row = self.selected_row()
        if not row or not row.get("installed"):
            self.message, self.error = "Select an installed user plugin first.", True
            return
        answer = self.prompt("Move {} to plugin trash? [y/N] ".format(row["entry"]["id"]))
        if answer.casefold() != "y":
            self.message, self.error = "Removal cancelled.", False
            return
        try:
            self.message = remove(row)
            self.dirty = True
            self.error = False
            self.rebuild()
        except Exception as exc:
            self.message, self.error = str(exc), True

    def action_update_all(self):
        updates = [row for row in self.rows if row["state"] == "UPDATE" and row["entry"]["id"] != "community-store"]
        if not updates:
            self.message, self.error = "No community plugin updates available.", False
            return
        answer = self.prompt("Update {} plugins? [y/N] ".format(len(updates)))
        if answer.casefold() != "y":
            self.message, self.error = "Update cancelled.", False
            return
        failed = []
        for index, row in enumerate(updates, 1):
            self.message = "Updating {} ({}/{})...".format(row["entry"]["id"], index, len(updates))
            self.draw()
            try:
                install(row)
                self.dirty = True
            except Exception as exc:
                failed.append(row["entry"]["id"] + ": " + str(exc))
        self.message = "Updated {} plugins".format(len(updates) - len(failed))
        if failed:
            self.message += "; failed: " + ", ".join(failed)
        self.error = bool(failed)
        self.rebuild()

    def action_update_store(self):
        row = next((item for item in self.rows if item["entry"]["id"] == "community-store"), None)
        if not row or row["state"] != "UPDATE":
            self.message, self.error = "Community Store is up to date or absent from registry.", False
            return
        answer = self.prompt("Update Community Store to {}? [y/N] ".format(row["entry"].get("version", "?")))
        if answer.casefold() != "y":
            self.message, self.error = "Store update cancelled.", False
            return
        try:
            self.message = install(row)
            self.dirty = True
            self.error = False
            self.message += " · restart AngelOS to reload Store"
            self.rebuild()
        except Exception as exc:
            self.message, self.error = str(exc), True

    def run(self):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        self.screen.keypad(True)
        while self.running:
            self.draw()
            key = self.screen.getch()
            if key in (ord("q"), 27):
                self.running = False
            elif key in (curses.KEY_UP, ord("k")):
                self.selected = max(0, self.selected - 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.selected = min(max(0, len(self.rows) - 1), self.selected + 1)
            elif key in (10, 13, curses.KEY_ENTER):
                self.action_install()
            elif key == ord("d"):
                self.action_remove()
            elif key == ord("U"):
                self.action_update_all()
            elif key == ord("s"):
                self.action_update_store()
            elif key == ord("r"):
                self.refresh()
            elif key == ord("/"):
                self.query = self.prompt("Search name/author/description/tag: ")
                self.rebuild()
            elif key == ord("a"):
                self.view = "ALL"
                self.rebuild()
            elif key == ord("i"):
                self.view = "INSTALLED"
                self.rebuild()
            elif key == ord("v"):
                self.view = "UPDATES"
                self.rebuild()
        if self.dirty:
            self.screen.addstr(max(0, self.screen.getmaxyx()[0] - 2), 0, "Changes made. Restart AngelOS to reload installed plugins.")
            self.screen.refresh()
            time.sleep(1.5)
            subprocess.run(["angelos", "restart"], check=False)


def main():
    ensure_launcher()
    try:
        curses.wrapper(lambda screen: StoreUI(screen).run())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
