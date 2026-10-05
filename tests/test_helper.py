import contextlib
import fcntl
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load('store_helper', 'scripts/community-store.py')
tui = load('store_tui', 'scripts/community-store-tui.py')
ENTRY = dict(id='example', name='Example', version='1.0.0', source='https://example.com/plugin.zip', status='approved')


def archive(files=None, version='1.0.0'):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as zf:
        zf.writestr('manifest.json', json.dumps(dict(id='example', name='Example', version=version)))
        zf.writestr('Main.qml', 'new content')
        script = zipfile.ZipInfo('run.sh')
        script.external_attr = (stat.S_IFREG | 0o755) << 16
        zf.writestr(script, '#!/bin/sh\nexit 0\n')
        for name, body in (files or {}).items():
            zf.writestr(name, body)
    return data.getvalue()


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(helper.Path, 'home', return_value=self.home).start()
        self.out, self.err = io.StringIO(), io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.out))
        self.enterContext(contextlib.redirect_stderr(self.err))
        self.target = self.home / '.config/angelos/plugins/example'
        self.target.mkdir(parents=True)
        (self.target / 'Main.qml').write_text('old content')

    def response(self, data):
        return patch.object(helper.urllib.request, 'urlopen', return_value=io.BytesIO(data))

    def install(self, data):
        with self.response(data):
            return helper.main(['install', ENTRY['source'], 'example', '1.0.0'])

    def test_install_preserves_backup_and_executable_scripts(self):
        self.assertEqual(self.install(archive()), 0)
        self.assertEqual((self.target / 'Main.qml').read_text(), 'new content')
        self.assertTrue((self.target / 'run.sh').stat().st_mode & stat.S_IXUSR)
        backups = list((self.home / '.local/state/angelos/plugin-trash').glob('*/Main.qml'))
        self.assertEqual([path.read_text() for path in backups], ['old content'])

    def test_failed_replacement_rolls_back_and_cleans_staging(self):
        replace = os.replace
        def failing_replace(source, dest):
            if Path(source).name == 'staged':
                raise OSError('simulated disk failure')
            return replace(source, dest)
        with patch.object(helper.os, 'replace', side_effect=failing_replace):
            self.assertEqual(self.install(archive()), 1)
        self.assertEqual((self.target / 'Main.qml').read_text(), 'old content')
        self.assertFalse(list(self.target.parent.glob('.community-store-*')))
        self.assertFalse(list(self.target.parent.glob('*.previous-*')))
        self.assertNotIn('Traceback', self.err.getvalue())

    def test_trash_failure_retains_backup_without_losing_successful_install(self):
        with patch.object(helper.shutil, 'move', side_effect=OSError('trash unavailable')):
            self.assertEqual(self.install(archive()), 0)
        backups = list(self.target.parent.glob('.example.previous-*/Main.qml'))
        self.assertEqual([p.read_text() for p in backups], ['old content'])
        self.assertEqual((self.target / 'Main.qml').read_text(), 'new content')

    def test_backup_moves_across_filesystems(self):
        with patch.object(helper.os, 'rename', side_effect=OSError(errno.EXDEV, 'cross-device link')):
            self.assertEqual(self.install(archive()), 0)
        backups = list((self.home / '.local/state/angelos/plugin-trash').glob('*/Main.qml'))
        self.assertEqual([path.read_text() for path in backups], ['old content'])

    def test_symbolic_link_archive_is_rejected(self):
        data = io.BytesIO(archive())
        with zipfile.ZipFile(data, 'a') as zf:
            link = zipfile.ZipInfo('link')
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(link, '/tmp/elsewhere')
        self.assertEqual(self.install(data.getvalue()), 1)
        self.assertEqual((self.target / 'Main.qml').read_text(), 'old content')

    def test_corrupt_archive_leaves_old_install_intact(self):
        self.assertEqual(self.install(b'not a zip'), 1)
        self.assertEqual((self.target / 'Main.qml').read_text(), 'old content')
        self.assertNotIn('Traceback', self.err.getvalue())

    def test_invalid_version_leaves_old_install_intact(self):
        self.assertEqual(self.install(archive(version='2.0.0')), 1)
        self.assertEqual((self.target / 'Main.qml').read_text(), 'old content')

    def test_archive_traversal_is_rejected(self):
        self.assertEqual(self.install(archive({'../escape.txt': 'bad'})), 1)
        self.assertEqual((self.target / 'Main.qml').read_text(), 'old content')

    def test_second_installer_is_rejected_before_download(self):
        with (self.target.parent / '.example.install.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(helper.urllib.request, 'urlopen') as download:
                self.assertEqual(helper.install(ENTRY['source'], 'example', '1.0.0'), 1)
                download.assert_not_called()
        self.assertEqual(self.install(archive()), 0)

    def test_valid_registry(self):
        with self.response(json.dumps(dict(version=1, plugins=[ENTRY])).encode()):
            self.assertEqual(helper.main(['fetch', 'https://example.com/plugins.json']), 0)
        self.assertEqual(json.loads(self.out.getvalue())['plugins'], [ENTRY])

    def test_malformed_registry_is_reported_without_traceback(self):
        bad = [[], None, dict(version=1, plugins=[ENTRY, ENTRY])]
        for field, value in [('tags', 'widgets'), ('tags', [None]), ('name', {}), ('version', None), ('description', []), ('source', 1)]:
            bad.append(dict(version=1, plugins=[{**ENTRY, field: value}]))
        for payload in bad:
            with self.subTest(payload=payload), self.response(json.dumps(payload).encode()):
                self.assertEqual(helper.main(['fetch', 'https://example.com/plugins.json']), 1)
        self.assertNotIn('Traceback', self.err.getvalue())


class TuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plugins = self.root / 'plugins'
        self.plugins.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(tui, 'PLUGIN_DIR', self.plugins).start()
        patch.object(tui, 'TRASH_DIR', self.root / 'trash').start()

    def manifest(self, folder, value):
        path = self.plugins / folder
        path.mkdir()
        (path / 'manifest.json').write_text(json.dumps(value))

    def test_localized_and_broken_manifests(self):
        self.manifest('example', dict(id='example', name={'ru': 'Пример'}, description={'en': 'Example'}))
        self.manifest('broken', [])
        self.manifest('mismatch', dict(id='../outside', name='Unsafe'))
        self.manifest('.example.previous-123', dict(id='example', name='Old'))
        rows = tui.plugin_rows([])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['entry']['name'], 'Пример')
        self.assertEqual(rows[0]['entry']['description'], 'Example')

    def test_equivalent_versions_do_not_offer_an_update(self):
        self.assertFalse(tui.is_update({'version': '1.0'}, {'version': '1.0.0'}))
        self.assertTrue(tui.is_update({'version': '1.0.0'}, {'version': '1.0.1'}))

    def test_self_removal_and_invalid_ids_are_blocked(self):
        for plugin_id in ['community-store', '../outside', '/tmp/outside']:
            with self.subTest(plugin_id=plugin_id), self.assertRaises(RuntimeError):
                tui.remove({'entry': {'id': plugin_id}, 'installed': {'id': plugin_id}})

    def test_removal_keeps_both_backups_in_same_second(self):
        row = {'entry': {'id': 'example'}, 'installed': {'id': 'example'}}
        for _ in range(2):
            self.manifest('example', row['installed'])
            tui.remove(row)
        self.assertEqual(len(list((self.root / 'trash').iterdir())), 2)


if __name__ == '__main__':
    unittest.main()
