"""Run the production drop target in Qt and verify URI selection/signals."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ZipDropTests(unittest.TestCase):
    def test_drop_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copyfile(ROOT / 'components/ZipDropArea.qml', root / 'ZipDropArea.qml')
            (root / 'tst_drop.qml').write_text('''import QtQuick
import QtTest
TestCase {
    name: "ZipDrop"
    ZipDropArea { id: target }
    SignalSpy { id: selected; target: target; signalName: "fileSelected" }
    SignalSpy { id: rejected; target: target; signalName: "rejected" }
    function init() { selected.clear(); rejected.clear(); }
    function test_encoded_local_file() {
        const uri = "file:///tmp/%D0%BF%D0%BB%D0%B0%D0%B3%D0%B8%D0%BD%20%231.ZIP";
        verify(target.select([uri]));
        compare(selected.count, 1);
        compare(selected.signalArguments[0][0], uri);
    }
    function test_invalid_drops() {
        for (const urls of [[], ["file:///a.zip","file:///b.zip"], ["https://example.com/a.zip"], ["file://server/a.zip"], ["file:///tmp/image.png"], ["file:///tmp/a.zip?x=1"]]) {
            verify(!target.select(urls));
        }
        compare(selected.count, 0);
        compare(rejected.count, 6);
    }
}''')
            runner = shutil.which('qmltestrunner6') or '/usr/lib/qt6/bin/qmltestrunner'
            result = subprocess.run([runner, '-input', str(root)], capture_output=True, text=True,
                                    env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'}, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
