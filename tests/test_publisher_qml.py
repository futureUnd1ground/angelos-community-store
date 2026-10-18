import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PublisherQmlTests(unittest.TestCase):
    def test_publication_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(name, content):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
            source=(ROOT/'services/Publisher.qml').read_text().replace('id: root','id: root\n    property alias testAuth: auth\n    property alias testPublish: publisher',1)
            write('Publisher.qml',source)
            write('qmldir','singleton Publisher 1.0 Publisher.qml\n')
            write('imports/Quickshell/qmldir','module Quickshell\nSingleton 1.0 Singleton.qml\n')
            write('imports/Quickshell/Singleton.qml','import QtQuick\nItem {}')
            write('imports/Quickshell/Io/qmldir','module Quickshell.Io\nProcess 1.0 Process.qml\nStdioCollector 1.0 StdioCollector.qml\n')
            write('imports/Quickshell/Io/Process.qml','import QtQuick\nItem { property var command: []; property bool running: false; property QtObject stdout; property QtObject stderr; signal exited(int code) }')
            write('imports/Quickshell/Io/StdioCollector.qml','import QtQuick\nQtObject { property string text: "" }')
            write('tst_publisher.qml','''import QtQuick
import QtTest
import "."
TestCase {
 name: "ZipPublisher"
 function init() {
   Publisher.testAuth.running=false; Publisher.testPublish.running=false;
   Publisher.plugin={dir:"/store"}; Publisher.login=""; Publisher.error="";
 }
 function test_auth_and_publication() {
   Publisher.checkAuth(); verify(Publisher.busy);
   compare(Publisher.testAuth.command,["python3","/store/scripts/publish-plugin.py","auth"]);
   Publisher.testAuth.stdout.text=JSON.stringify({login:"alice"});
   Publisher.testAuth.running=false; Publisher.testAuth.exited(0);
   compare(Publisher.login,"alice");
   verify(Publisher.publish("file:///tmp/plugin%20name.zip"));
   compare(Publisher.testPublish.command,["python3","/store/scripts/publish-plugin.py","publish","file:///tmp/plugin%20name.zip"]);
   verify(!Publisher.publish("/tmp/second.zip"));
   Publisher.testPublish.stdout.text=JSON.stringify({message:"Submitted",url:"https://github.com/test/pull/1",release:"https://github.com/test/releases/tag/v1"});
   Publisher.testPublish.running=false; Publisher.testPublish.exited(0);
   compare(Publisher.prUrl,"https://github.com/test/pull/1"); compare(Publisher.error,"");
 }
 function test_failure_preserves_readable_error() {
   verify(!Publisher.publish("  "));
   verify(Publisher.publish("/tmp/bad.zip"));
   Publisher.testPublish.stderr.text="Bad archive";
   Publisher.testPublish.running=false; Publisher.testPublish.exited(1);
   compare(Publisher.error,"Bad archive"); compare(Publisher.prUrl,"");
 }
}''')
            r=subprocess.run(['/usr/lib/qt6/bin/qmltestrunner','-input',tmp,'-import',str(root/'imports')],capture_output=True,text=True,env={**os.environ,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'},timeout=30)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
