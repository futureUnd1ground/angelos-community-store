# AngelOS Community Store

[Русская версия](README.ru.md) | English

An independent AngelOS plugin that uses the native plugin directory and
`Plugins` service. It is installed like any other user plugin and does not
modify AngelOS upstream.

## Install

From a terminal, download the reviewed installer and run it:

```bash
curl -fsSL -o /tmp/install-community-store.py \
  https://raw.githubusercontent.com/futureUnd1ground/angelos-community-store/main/install-community-store.py
python3 /tmp/install-community-store.py
```

Fish users can run the native Fish entry point:

```fish
curl -fsSL -o /tmp/install-community-store.fish \
  https://raw.githubusercontent.com/futureUnd1ground/angelos-community-store/main/install-community-store.fish
and fish /tmp/install-community-store.fish
```

It downloads the same verified Python installer to a temporary file, installs
the Store, adds `~/.local/bin` to Fish's PATH, and removes the temporary file.
The two steps are kept separate so the downloaded installer can be inspected
before running it.

The installer downloads the pinned release over HTTPS, validates its archive
and manifest, installs it atomically in `~/.config/angelos/plugins`, creates
the `community-store` command, and restarts AngelOS. Use
`--no-restart` when restarting manually. Review the script before running it;
it never executes a shell pipeline.

Copy this directory to `~/.config/angelos/plugins/community-store/`, or use
AngelOS Plugin Studio to install the files. Then reload the shell and open
**Settings -> Plugins -> Community Store**.

## Terminal interface

The store also has a standalone TUI and does not require the Settings GUI:

```bash
python3 ~/.config/angelos/plugins/community-store/scripts/community-store-tui.py
```

The first run creates `~/.local/bin/community-store`, so later runs are:

```bash
community-store
```

Keys: `j/k` or arrows move, `Enter` installs or updates the selected plugin,
`d` removes it to AngelOS plugin-trash, `U` updates all community plugins,
`s` updates the Store itself, `r` refreshes the registry, `/` searches, `a`
shows all, `i` shows installed, `v` shows updates, and `q` exits. Changes
restart AngelOS after the TUI closes.

After a successful plugin install or update, the AngelOS shell restarts
automatically so its components are loaded. A batch update triggers one restart
after the queue completes.

## Install from the Run launcher

Open the app launcher (`Mod+Space`), type `plugins` followed by part of a
plugin's name, author, description, or tag, then select `Install`, `Update`,
or `Remove`. Removal uses AngelOS's native plugin trash behavior.
The page is also available at **Settings -> Plugins -> Community Store**. The
shell restarts after updates to load the changed plugin components.

The default registry is the raw `plugins.json` in
`https://github.com/futureUnd1ground/angelos-community-registry`. The URL can
be changed in the page.

## Registry entries

Use an HTTPS ZIP release with a top-level `manifest.json` (or one directory
containing it). The registry `id` and `version` must match that manifest. The
installer rejects path traversal, malformed manifests, mismatched IDs or
versions, non-HTTPS sources, and archives over 64 MiB.

## Publish a plugin to the catalog

1. Keep the plugin source in its own GitHub repository. Its AngelOS
   `manifest.json` must have a unique `id` and a `version` matching the
   release you publish.
2. Create a ZIP containing the plugin folder and publish it as an asset on a
   GitHub Release. The ZIP must contain exactly one `manifest.json`, either
   at its root or one directory below it.
3. Fork
   [angelos-community-registry](https://github.com/futureUnd1ground/angelos-community-registry),
   add an entry to `plugins.json` with `status` set to `pending`, and open a
   pull request. Include the source URL, repository, author, description,
   tags, license, dependencies, and requested permissions.
4. The registry maintainer reviews the code, license, ZIP, and compatibility.
   After approval, the maintainer changes `status` to `approved` and merges
   the pull request. Approved entries appear after **Refresh** in Community
   Store.

The registry owner moderates listings through GitHub pull requests. Pending
entries are not shown in the Store; changing an approved entry back to
`pending` hides it on the next registry refresh.

## Browse installed plugins

The **Installed plugins** section lists plugins discovered by AngelOS,
including built-in and user plugins. From a row you can enable or disable the
plugin, open its details or directory, and remove a user plugin. Built-in
plugins are hidden using AngelOS's native remove behavior; their files remain
part of the AngelOS installation.

## AngelOS categories

Market 0.8.0 groups filters into Story & games, Appearance, and Plugins & tools. The taxonomy follows AngelOS's existing realms and circles, visual novel, characters, scenes and voices, alongside palettes, skins, wallpapers, cursors, fonts, icons and effects.

| `category` | Store label |
| --- | --- |
| `Story` | Story |
| `Novels` | Visual novels |
| `Quests` | Quests |
| `Characters` | Characters |
| `Realms` | Worlds & realms |
| `Dialogue` | Dialogue & scenes |
| `Minigames` | Minigames |
| `Voices` | Voices |
| `Pets` | Pets |
| `Widgets` | Widgets |
| `Desktop` | Desktop |
| `Bar` | Bar |
| `Themes` | Themes |
| `Skins` | Interface skins |
| `Wallpapers` | Wallpapers |
| `Cursors` | Cursors |
| `Fonts` | Fonts |
| `Icons` | Icons |
| `Effects` | Effects & animations |
| `AI` | AI assistants |
| `DeveloperTools` | Developer tools |
| `Launcher` | Launcher & search |
| `Network` | Network |
| `Audio` | Music & audio |
| `Productivity` | Productivity |
| `Integrations` | Integrations |
| `Accessibility` | Accessibility |
| `System` | System |
| `Utilities` | Utilities |

Use one primary category ID and tags for other applicable filters. The registry uses stable English IDs; Store translates their labels. Legacy categories and tags remain supported, including Worlds, Narrative, Lore and story-packs. Unknown categories are listed automatically under Plugins & tools.

Story collects stories, novels, quests, characters, realms, dialogue and voices. Ordinary pets and minigames require an explicit story tag to enter that filter. Themes collects appearance subcategories. Search supports both Russian and English category labels.

Story example: `"category": "Story", "tags": ["story", "novel", "dialogue", "characters", "heaven"]`. Appearance example: `"category": "Skins", "tags": ["skins", "themes", "fonts", "cursor"]`. Category metadata does not load story content into the engine; plugin authors must implement integration through AngelOS's supported APIs and document compatibility and dependencies.

## Install a local ZIP

Open “Установить из ZIP” in Community Store settings, drop one ready plugin ZIP onto the field and click “Установить ZIP”. An absolute file path can also be pasted manually. The ID and version come from `manifest.json` at the archive root or inside a single plugin folder. AngelOS restarts the shell after successful installation to load the plugin components.

Local installation works offline and shares archive size/path/symlink checks, per-plugin locking, backups and rollback with registry installation. Terminal usage: `python3 scripts/community-store.py install-local /path/plugin.zip`.
