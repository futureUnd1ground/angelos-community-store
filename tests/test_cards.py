"""Run the real card components offscreen with minimal AngelOS service doubles."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

RUNNER = os.environ.get('QMLTESTRUNNER') or shutil.which('qmltestrunner6') or ('/usr/lib/qt6/bin/qmltestrunner' if Path('/usr/lib/qt6/bin/qmltestrunner').exists() else shutil.which('qmltestrunner'))
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(RUNNER, 'qmltestrunner is required')
class CardTests(unittest.TestCase):
    def test_details_open_repository_from_both_import_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(path, text):
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text)
            for name in ('PluginCard', 'InstalledPluginCard'):
                for prefix in ('', 'components/'):
                    dest = root / (prefix + name + '.qml')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / (prefix + name + '.qml'), dest)
            write('imports/Quickshell/qmldir', 'module Quickshell\nsingleton Quickshell 1.0 Quickshell.qml\n')
            write('imports/Quickshell/Quickshell.qml', '''pragma Singleton
import QtQuick
QtObject {
    property var command: []
    function execDetached(args) { command = args }
}''')
            write('imports/qs/config/qmldir', 'module qs.config\nsingleton Theme 1.0 Theme.qml\n')
            write('imports/qs/config/Theme.qml', '''pragma Singleton
import QtQuick
QtObject {
    property int u: 2
    property color face: "white"
    property color textDim: "gray"
    property color accent: "blue"
}''')
            widgets = {
                'PxBox': 'Rectangle {}',
                'PxText': 'Text { property string kind; property bool dim }',
                'PxIcon': 'Item { property string name; property real pixel }',
                'PxButton': '''Item { property string text; property string icon
                    property bool compact; property bool danger; property bool checked
                    implicitWidth: 90; implicitHeight: 24; signal clicked() }''',
                'PxToggle': 'Item { property bool checked; property string text; signal toggled(bool checked) }',
            }
            write('imports/qs/widgets/qmldir', 'module qs.widgets\n' + ''.join(f'{name} 1.0 {name}.qml\n' for name in widgets))
            for name, body in widgets.items():
                write(f'imports/qs/widgets/{name}.qml', 'import QtQuick\n' + body)
            services = {
                'Plugins': 'function isEnabled(entry) { return true }\nfunction setEnabled(id, value) {}',
                'I18n': 'function label(value) { return String(value) }',
                'Shell': 'function openPath(value) {}',
            }
            write('imports/qs/services/qmldir', 'module qs.services\n' + ''.join(f'singleton {name} 1.0 {name}.qml\n' for name in services))
            for name, body in services.items():
                write(f'imports/qs/services/{name}.qml', 'pragma Singleton\nimport QtQuick\nQtObject {\n' + body + '\n}')
            write('services/qmldir', 'singleton Registry 1.0 Registry.qml\n')
            write('services/Registry.qml', '''pragma Singleton
import QtQuick
QtObject {
    property int revision: 0
    property bool busy: false
    property var entries: [{id: "test-plugin", repository: "https://github.com/example/catalog"}]
    function installed(id) { return null }
    function version(id) { return "1.0.0" }
    function newer(a, b) { return false }
}''')
            write('tst_cards.qml', '''import QtQuick
import QtTest
import Quickshell
import "." as Legacy
import "components" as Cards
TestCase {
    name: "DetailsNavigation"
    Component { id: legacyCatalog; Legacy.PluginCard {} }
    Component { id: legacyInstalled; Legacy.InstalledPluginCard {} }
    Component { id: catalog; Cards.PluginCard {} }
    Component { id: installed; Cards.InstalledPluginCard {} }
    function button(item) {
        if (item.text === "Подробнее") return item
        const children = item.children || []
        for (let i = 0; i < children.length; ++i) {
            const found = button(children[i])
            if (found) return found
        }
        return null
    }
    function test_navigation_data() {
        return [
            {tag: "legacy catalog", component: legacyCatalog, entry: {id: "example", repository: "https://github.com/example/plugin"}, url: "https://github.com/example/plugin"},
            {tag: "catalog", component: catalog, entry: {id: "example", repository: "https://github.com/example/plugin"}, url: "https://github.com/example/plugin"},
            {tag: "legacy installed", component: legacyInstalled, entry: {id: "test-plugin"}, url: "https://github.com/example/catalog"},
            {tag: "installed", component: installed, entry: {id: "test-plugin"}, url: "https://github.com/example/catalog"},
            {tag: "store fallback", component: legacyInstalled, entry: {id: "community-store"}, url: "https://github.com/futureUnd1ground/angelos-community-store"},
            {tag: "missing URL", component: legacyCatalog, entry: {id: "example"}, url: ""}
        ]
    }
    function test_navigation(data) {
        const card = createTemporaryObject(data.component, this, {entry: data.entry})
        verify(card !== null)
        const details = button(card)
        verify(details !== null, "Details button must use the maintained implementation")
        compare(details.enabled, data.url !== "")
        if (data.url) {
            details.clicked()
            compare(Quickshell.command, ["xdg-open", data.url])
        }
    }
}''')
            result = subprocess.run([RUNNER, '-input', str(root), '-import', str(root / 'imports')],
                                    env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QPA_PLATFORMTHEME': '', 'QT_QUICK_BACKEND': 'software', 'QT_FORCE_STDERR_LOGGING': '1', 'QT_LOGGING_TO_CONSOLE': '1'}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
