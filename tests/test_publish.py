"""Publication planning and GitHub orchestration with isolated network/command doubles."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publisher', ROOT / 'scripts/publish-plugin.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = dict(id='example', name='Пример', version='1.0.0', description='Описание', settings='Settings.qml')
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as z:
            z.writestr('manifest.json', json.dumps(self.manifest))
            z.writestr('Settings.qml', 'import QtQuick\nItem {}')
        self.path = self.root / 'пример с пробелами.zip'; self.path.write_bytes(data.getvalue())
        self.digest = hashlib.sha256(data.getvalue()).hexdigest()
        self.payload = {'version': 1, 'plugins': []}
        self.commands = []; self.release_created = False; self.old_prs = []
        self.addCleanup(patch.stopall)
        patch.object(publisher, 'account', return_value='alice').start()
        patch.object(publisher, 'api', side_effect=self.api).start()
        patch.object(publisher, 'gh', side_effect=self.gh).start()
        patch.object(publisher, 'git', side_effect=lambda *args, **kwargs: self.commands.append(('git', args))).start()
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def api(self, path):
        if path.endswith('/git/ref/heads/main'): return {'object': {'sha': 'abc123'}}
        if '/contents/plugins.json?ref=abc123' in path:
            return {'content': base64.b64encode(json.dumps(self.payload).encode()).decode()}
        if '/contents/plugins.json?ref=publish-' in path: return None
        if '/git/ref/tags/' in path: return None
        if '/releases/tags/' in path:
            if not self.release_created: return None
            return {'body': 'AngelOS ZIP SHA256: ' + self.digest, 'html_url': 'https://github.com/alice/angelos-example/releases/tag/v1.0.0',
                    'assets': [{'name': 'example-v1.0.0.zip', 'browser_download_url': 'https://github.com/alice/angelos-example/releases/download/v1.0.0/example-v1.0.0.zip'}]}
        if path == 'repos/alice/angelos-example': return None
        raise AssertionError(path)

    def gh(self, *args):
        self.commands.append(('gh', args))
        if args[:2] == ('pr', 'list'): return json.dumps(self.old_prs)
        if args[:2] == ('release', 'create'):
            self.release_created = True
            self.assertEqual(Path(args[3]).read_bytes(), self.path.read_bytes())
        if args[:2] == ('pr', 'create'):
            self.assertEqual(args[args.index('--base') + 1], 'main')
            body = Path(args[args.index('--body-file') + 1])
            candidate = json.loads((body.parent / 'registry/plugins.json').read_text())
            self.assertEqual(candidate['plugins'][-1]['status'], 'pending')
            self.assertEqual(candidate['plugins'][-1]['id'], 'example')
            self.assertIn(self.digest, body.read_text())
            return 'https://github.com/futureUnd1ground/angelos-community-registry/pull/123'
        return ''

    def test_complete_publication_targets_main_with_pending_status(self):
        result = publisher.publish(self.path.as_uri())
        self.assertTrue(result['url'].endswith('/123'))
        self.assertTrue(any(args[:2] == ('repo','create') for command, args in self.commands if command == 'gh'))
        self.assertFalse(any('merge' in args or 'approve' in args for _, args in self.commands))

    def test_retry_reuses_open_pr_without_new_writes(self):
        self.old_prs = [{'state': 'OPEN', 'url': 'https://github.com/test/pull/1'}]
        result = publisher.publish(str(self.path))
        self.assertEqual(result['url'], self.old_prs[0]['url'])
        self.assertEqual(len(self.commands), 1)

    def test_closed_pr_requires_new_version(self):
        self.old_prs = [{'state': 'CLOSED', 'url': 'https://github.com/test/pull/1'}]
        with self.assertRaisesRegex(ValueError, 'закрыта'):
            publisher.publish(str(self.path))
        self.assertEqual(len(self.commands), 1)

    def test_foreign_plugin_id_cannot_be_republished(self):
        self.payload['plugins'] = [{'id':'example', 'repository':'https://github.com/bob/example'}]
        with self.assertRaisesRegex(ValueError, 'твой репозиторий'):
            publisher.publish(str(self.path))
        self.assertEqual(self.commands, [])

    def test_missing_entrypoint_rejected_before_github(self):
        self.manifest['launcher'] = 'Missing.qml'
        with self.assertRaisesRegex(ValueError, 'отсутствует'):
            publisher.validate_publication(self.manifest, self.root)

    def test_invalid_metadata_rejected(self):
        for field, value in [('version','bad'), ('tags','search'), ('permissions',[None]), ('description','')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                publisher.validate_publication({**self.manifest,field:value},self.root)

    def test_repository_must_be_owned_and_separate_from_registry(self):
        with self.assertRaises(ValueError):
            publisher.repository_for({**self.manifest,'repository':'https://github.com/bob/example'},'alice')
        with self.assertRaises(ValueError):
            publisher.repository_for({**self.manifest,'repository':'https://github.com/' + publisher.REGISTRY},'futureUnd1ground')

    def test_existing_release_with_other_bytes_is_rejected(self):
        with patch.object(publisher,'optional_api',return_value={'body':'other bytes'}):
            with self.assertRaisesRegex(ValueError, 'номер версии'):
                publisher.ensure_release('alice/example',self.root,self.path,self.manifest,self.digest,'alice')
        self.assertEqual(self.commands, [])

    def test_corrupt_zip_is_reported_without_traceback(self):
        self.path.write_bytes(b'broken')
        with patch.dict('os.environ',{'XDG_STATE_HOME':str(self.root / 'state')}):
            self.assertEqual(publisher.main(['publish',str(self.path)]),1)
        self.assertEqual(self.commands, [])

    def test_git_internal_files_rejected_before_commands(self):
        with zipfile.ZipFile(self.path, 'a') as z:z.writestr('.git/config','bad')
        with self.assertRaisesRegex(ValueError, 'Git internal'):
            publisher.publish(str(self.path))
        self.assertEqual(self.commands, [])

if __name__ == '__main__': unittest.main()
