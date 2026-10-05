"""Execute the production Registry QML with deterministic process/service doubles."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = os.environ.get('QMLTESTRUNNER') or shutil.which('qmltestrunner6') or ('/usr/lib/qt6/bin/qmltestrunner' if Path('/usr/lib/qt6/bin/qmltestrunner').exists() else shutil.which('qmltestrunner'))


@unittest.skipUnless(RUNNER, 'Qt 6 qmltestrunner is required')
class RegistryTests(unittest.TestCase):
    def test_registry_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(path, text):
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text)
            source = (ROOT / 'services/Registry.qml').read_text()
            # Expose only test handles; execute all production handlers unchanged.
            source = source.replace('id: root', '''id: root
    property alias testInstaller: installer
    property alias testFetcher: fetcher
    property alias testNext: nextInstall
    property alias testRestart: shellRestart''', 1)
            write('Registry.qml', source)
            write('qmldir', 'singleton Registry 1.0 Registry.qml\n')
            write('imports/Quickshell/qmldir', 'module Quickshell\nSingleton 1.0 Singleton.qml\nsingleton Quickshell 1.0 Quickshell.qml\n')
            write('imports/Quickshell/Singleton.qml', 'import QtQuick\nItem {}')
            write('imports/Quickshell/Quickshell.qml', 'pragma Singleton\nimport QtQuick\nQtObject { function execDetached(args) {} }')
            write('imports/Quickshell/Io/qmldir', 'module Quickshell.Io\nProcess 1.0 Process.qml\nStdioCollector 1.0 StdioCollector.qml\n')
            write('imports/Quickshell/Io/Process.qml', '''import QtQuick
Item {
    property var command: []
    property bool running: false
    property QtObject stdout
    property QtObject stderr
    signal exited(int code)
}''')
            write('imports/Quickshell/Io/StdioCollector.qml', 'import QtQuick\nQtObject { property string text: "" }')
            write('imports/qs/config/qmldir', 'module qs.config\nTheme 1.0 Theme.qml\n')
            write('imports/qs/config/Theme.qml', 'import QtQuick\nQtObject {}')
            write('imports/qs/services/qmldir', 'module qs.services\nsingleton Plugins 1.0 Plugins.qml\n')
            write('imports/qs/services/Plugins.qml', '''pragma Singleton
import QtQuick
QtObject {
    property bool scanning: false
    property var plugins: [{id: "example", version: "1.0.0"}, {id: "other", version: "1.0.0"}]
    property string removed: ""
    function byId(id) { return plugins.find(p => p.id === id) || null }
    function reload() {}
    function remove(id) { removed = id }
}''')
            matches = re.search(r'    function matches\(entry\) \{.*?\n    \}', (ROOT / 'Settings.qml').read_text(), re.S).group()
            write('tst_registry.qml', '''import QtQuick
import QtTest
import qs.services
import "."
TestCase {
    name: "RegistryOperations"
    QtObject {
        id: page
        property string search: ""
        property string category: "All"
MATCHES
    }
    function init() {
        Registry.autoUpdate = false
        Registry.testNext.stop()
        Registry.testRestart.stop()
        Registry.testInstaller.running = false
        Registry.testFetcher.running = false
        Registry.batchActive = false
        Registry.automaticRun = false
        Registry.autoUpdateAttempted = false
        Registry.batchFailed = 0
        Registry.batchDone = 0
        Registry.batchErrors = []
        Registry.updateQueue = []
        Registry.status = "idle"
        Plugins.scanning = false
        Plugins.removed = ""
        Registry.plugin = {dir: "/test", set: function(key, value) {}}
        Registry.entries = [{id: "example", name: "Example", version: "2.0.0", source: "https://example.com/plugin.zip"},
                            {id: "other", name: "Other", version: "2.0.0", source: "https://example.com/other.zip"}]
    }
    function cleanup() {
        Registry.autoUpdate = false
        Registry.testNext.stop()
        Registry.testRestart.stop()
    }
    function complete(code, message) {
        Registry.testInstaller.stdout.text = code === 0 ? message : ""
        Registry.testInstaller.stderr.text = code === 0 ? "" : message
        Registry.testInstaller.running = false
        Registry.testInstaller.exited(code)
        Registry.testNext.stop()
    }
    function test_batch_cannot_be_interrupted_between_steps() {
        Registry.updateAllPlugins(false)
        verify(Registry.testInstaller.running)
        complete(0, "Installed example")
        verify(Registry.busy)
        verify(!Registry.install(Registry.entries[0]))
        verify(!Registry.uninstall("example"))
        verify(!Registry.setRegistry("https://example.com/other.json"))
        Registry.fetch()
        verify(!Registry.testFetcher.running)
        compare(Plugins.removed, "")
        Registry.installNext()
        compare(Registry.testInstaller.command[4], "other")
    }
    function test_batch_retains_earlier_failure() {
        Registry.updateAllPlugins(false)
        complete(1, "download failed")
        Registry.installNext()
        complete(0, "Installed other")
        Registry.installNext()
        compare(Registry.status, "error")
        verify(Registry.error.indexOf("example: download failed") >= 0)
        compare(Registry.batchDone, 2)
        compare(Registry.batchFailed, 1)
        verify(!Registry.batchActive)
        verify(Registry.testRestart.running)
        verify(!Registry.install(Registry.entries[0]))
    }
    function test_auto_update_waits_for_scan_and_does_not_repeat() {
        Registry.status = "ready"
        Plugins.scanning = true
        Registry.autoUpdate = true
        Registry.maybeAutoUpdate()
        verify(!Registry.testInstaller.running)
        Plugins.scanning = false
        verify(Registry.testInstaller.running)
        complete(1, "download failed")
        Registry.installNext()
        complete(1, "download failed")
        Registry.installNext()
        Registry.maybeAutoUpdate()
        verify(!Registry.testInstaller.running)
        verify(!Registry.batchActive)
    }
    function test_fetch_blocks_manual_install() {
        Registry.fetch()
        verify(Registry.testFetcher.running)
        verify(!Registry.install(Registry.entries[0]))
        verify(!Registry.testInstaller.running)
    }
    function test_category_uses_registry_field() {
        page.category = "Widgets"
        page.search = ""
        verify(page.matches({name: "Cat", category: "Widgets", tags: ["widget", "pet"]}))
        verify(!page.matches({name: "Utility", category: "Utilities", tags: ["utility"]}))
        page.search = "missing"
        verify(!page.matches({name: "Cat", category: "Widgets", tags: ["widget"]}))
    }
}'''.replace('MATCHES', matches))
            result = subprocess.run([RUNNER, '-input', str(root), '-import', str(root / 'imports')],
                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QPA_PLATFORMTHEME': '', 'QT_QUICK_BACKEND': 'software', 'QT_FORCE_STDERR_LOGGING': '1', 'QT_LOGGING_TO_CONSOLE': '1'},
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
