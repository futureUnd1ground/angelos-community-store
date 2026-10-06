#!/usr/bin/env python3
"""Publish a validated local plugin ZIP as a public release and a pending registry PR."""
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

REGISTRY = 'futureUnd1ground/angelos-community-registry'
spec = importlib.util.spec_from_file_location('store_helper', Path(__file__).with_name('community-store.py'))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class CommandError(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__((result.stderr or result.stdout or 'GitHub command failed').strip())


def run(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise CommandError(result)
    return result.stdout.strip()


def gh(*args):
    return run(['gh', *args])


def api(path):
    return json.loads(gh('api', path))


def optional_api(path):
    try:
        return api(path)
    except CommandError as exc:
        if 'HTTP 404' in exc.result.stderr:
            return None
        raise


def account():
    if not shutil.which('gh'):
        raise RuntimeError('Установи GitHub CLI (gh), затем выполни gh auth login --web.')
    try:
        login = api('user')['login']
    except (CommandError, KeyError) as exc:
        raise RuntimeError('Нужен вход в GitHub: нажми «Войти в GitHub», затем «Проверить вход».') from exc
    return login


def progress(message):
    print(message, file=sys.stderr, flush=True)


def validate_publication(manifest, source_dir):
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', manifest['version']):
        raise ValueError('Для публикации укажи version в формате 1.0.0 в manifest.json.')
    if not isinstance(manifest.get('description'), str) or not manifest['description'].strip():
        raise ValueError('Добавь description в manifest.json перед публикацией.')
    for key in ('author', 'repository', 'category', 'license', 'icon'):
        if key in manifest and not isinstance(manifest[key], str):
            raise ValueError('Неверное поле manifest: ' + key)
    for key in ('tags', 'dependencies', 'permissions'):
        if key in manifest and (not isinstance(manifest[key], list) or
                                not all(isinstance(v, str) for v in manifest[key])):
            raise ValueError('Неверное поле manifest: ' + key)
    for key in ('main', 'settings', 'launcher', 'barWidget', 'desktopWidget', 'sidebarWidget', 'menuComponent'):
        if key not in manifest:
            continue
        value = manifest[key]
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ValueError('Неверная точка входа: ' + key)
        entry = (source_dir / value).resolve()
        if not entry.is_relative_to(source_dir.resolve()) or not entry.is_file():
            raise ValueError('Файл точки входа отсутствует в плагине: ' + key)


def repository_for(manifest, login, existing=None):
    url = manifest.get('repository') or (existing or {}).get('repository')
    if url:
        match = re.fullmatch(r'https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)/?', url)
        if not match or match[1].lower() != login.lower():
            raise ValueError('repository должен указывать на твой репозиторий GitHub.')
        repo = match[1] + '/' + match[2]
        if repo.lower() == REGISTRY.lower():
            raise ValueError('Для исходников плагина нужен отдельный репозиторий, не реестр.')
        return repo
    return login + '/angelos-' + manifest['id']


def listing(manifest, login, repo, asset):
    entry = {k: manifest[k] for k in ('id', 'name', 'version', 'description')}
    entry.update(author=manifest.get('author') or login, repository='https://github.com/' + repo,
                 source=asset, category=manifest.get('category') or 'Utilities',
                 tags=manifest.get('tags', []), dependencies=manifest.get('dependencies', []),
                 permissions=manifest.get('permissions', []), status='pending')
    for key in ('license', 'icon'):
        if manifest.get(key):
            entry[key] = manifest[key]
    return entry


# No shell interpolation: gh supplies its own credentials to Git's helper protocol.
def git(*args, cwd):
    return run(['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
                '-c', 'commit.gpgsign=false', *args], cwd=cwd)


def init_commit(directory, branch, login, message):
    git('-c', 'init.templateDir=', 'init', '-b', branch, cwd=directory)
    git('config', 'user.name', login, cwd=directory)
    git('config', 'user.email', login + '@users.noreply.github.com', cwd=directory)
    git('add', '--force', '--all', cwd=directory)
    git('commit', '-m', message, cwd=directory)


def ensure_release(repo, source_dir, archive, manifest, digest, login):
    version = manifest['version']
    tag = 'v' + version
    asset_name = manifest['id'] + '-v' + version + '.zip'
    marker = 'AngelOS ZIP SHA256: ' + digest
    release = optional_api('repos/' + repo + '/releases/tags/' + tag)
    if release:
        if marker not in (release.get('body') or ''):
            raise ValueError('Этот номер версии уже занят другим релизом. Увеличь version в manifest.json.')
        asset = next((a for a in release.get('assets', []) if a['name'] == asset_name), None)
        if asset:
            # Verify bytes before reusing a previously uploaded asset.
            with tempfile.TemporaryDirectory() as tmp:
                gh('release', 'download', tag, '--repo', repo, '--pattern', asset_name, '--dir', tmp)
                if hashlib.sha256((Path(tmp) / asset_name).read_bytes()).hexdigest() != digest:
                    raise ValueError('Архив этой версии на GitHub отличается. Увеличь version.')
            if release.get('draft'):
                gh('release', 'edit', tag, '--repo', repo, '--draft=false')
                release = api('repos/' + repo + '/releases/tags/' + tag)
            return asset['browser_download_url'], release['html_url']
        gh('release', 'upload', tag, str(archive), '--repo', repo)
        if release.get('draft'):
            gh('release', 'edit', tag, '--repo', repo, '--draft=false')
    else:
        if optional_api('repos/' + repo + '/git/ref/tags/' + tag):
            raise ValueError('Этот номер версии уже занят тегом GitHub. Увеличь version.')
        branch = 'angelos-release-' + version + '-' + digest[:12]
        init_commit(source_dir, branch, login, 'Release ' + manifest['id'] + ' ' + version)
        git('push', 'https://github.com/' + repo + '.git', 'HEAD:refs/heads/' + branch, cwd=source_dir)
        gh('release', 'create', tag, str(archive), '--repo', repo, '--target', branch,
           '--title', manifest['name'] + ' ' + version, '--notes', marker)
    release = api('repos/' + repo + '/releases/tags/' + tag)
    asset = next((a for a in release.get('assets', []) if a['name'] == asset_name), None)
    if not asset:
        raise RuntimeError('GitHub не вернул опубликованный ZIP; повтори публикацию.')
    return asset['browser_download_url'], release['html_url']


def publish(source):
    # Freeze and validate the selected bytes before the first GitHub mutation.
    with helper.local_path(source).open('rb') as file:
        data = file.read(helper.MAX_ARCHIVE + 1)
    digest = hashlib.sha256(data).hexdigest()
    with tempfile.TemporaryDirectory(prefix='angelos-publish-') as temp:
        work = Path(temp)
        source_dir, manifest = helper.unpack_plugin(data, work / 'unpacked')
        validate_publication(manifest, source_dir)
        login = account()
        progress('Проверяю запись в реестре…')
        base = api('repos/' + REGISTRY + '/git/ref/heads/main')['object']['sha']
        document = api('repos/' + REGISTRY + '/contents/plugins.json?ref=' + base)
        payload = json.loads(base64.b64decode(document['content']).decode('utf-8'))
        if not isinstance(payload, dict) or payload.get('version') != 1 or not isinstance(payload.get('plugins'), list):
            raise ValueError('Реестр содержит неверный JSON; публикация остановлена.')
        ids = [p.get('id') for p in payload['plugins'] if isinstance(p, dict)]
        if len(ids) != len(payload['plugins']) or len(ids) != len(set(ids)):
            raise ValueError('Реестр содержит неверные или повторяющиеся записи.')
        existing = next((p for p in payload['plugins'] if p['id'] == manifest['id']), None)
        repo = repository_for(manifest, login, existing)
        if existing and existing.get('repository', '').rstrip('/').lower() != ('https://github.com/' + repo).lower():
            raise ValueError('Этот ID уже занят другим плагином в реестре.')
        branch = 'publish-' + manifest['id'] + '-' + manifest['version'] + '-' + digest[:12]
        prs = json.loads(gh('pr', 'list', '--repo', REGISTRY, '--head', login + ':' + branch,
                            '--state', 'all', '--json', 'url,state'))
        if prs:
            if prs[0]['state'] == 'CLOSED':
                raise ValueError('Заявка этой версии закрыта. Исправь плагин и увеличь version.')
            return {'url': prs[0]['url'], 'id': manifest['id'], 'version': manifest['version'],
                    'message': 'Заявка уже существует.'}
        info = optional_api('repos/' + repo)
        if info is None:
            progress('Создаю публичный репозиторий исходников…')
            gh('repo', 'create', repo, '--public', '--description', manifest['description'][:200])
        elif info.get('private') or not info.get('permissions', {}).get('push'):
            raise ValueError('Для публикации нужен публичный репозиторий с правом записи.')
        progress('Публикую исходники и ZIP в GitHub Release…')
        asset_name = manifest['id'] + '-v' + manifest['version'] + '.zip'
        archive = work / asset_name
        archive.write_bytes(data)
        asset, release_url = ensure_release(repo, source_dir, archive, manifest, digest, login)
        entry = listing(manifest, login, repo, asset)
        if existing:
            payload['plugins'][payload['plugins'].index(existing)] = entry
        else:
            payload['plugins'].append(entry)
        progress('Создаю заявку на проверку в Community Registry…')
        registry_owner, registry_name = REGISTRY.split('/')
        fork = REGISTRY if login.lower() == registry_owner.lower() else login + '/' + registry_name
        if fork != REGISTRY:
            gh('repo', 'fork', REGISTRY, '--clone=false', '--remote=false')
        checkout = work / 'registry'
        checkout.mkdir()
        git('-c', 'init.templateDir=', 'init', '-b', branch, cwd=checkout)
        git('fetch', '--depth=1', 'https://github.com/' + REGISTRY + '.git', base, cwd=checkout)
        git('checkout', '-B', branch, 'FETCH_HEAD', cwd=checkout)
        git('config', 'user.name', login, cwd=checkout)
        git('config', 'user.email', login + '@users.noreply.github.com', cwd=checkout)
        (checkout / 'plugins.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
        git('add', 'plugins.json', cwd=checkout)
        git('commit', '-m', 'Submit ' + manifest['id'] + ' ' + manifest['version'], cwd=checkout)
        # Reuse a branch left by an interrupted PR creation only if its bytes agree.
        previous = optional_api('repos/' + fork + '/contents/plugins.json?ref=' + branch)
        if previous:
            if base64.b64decode(previous['content']) != (checkout / 'plugins.json').read_bytes():
                raise ValueError('Ветка заявки уже содержит другие изменения. Открой её на GitHub для проверки.')
        else:
            git('push', 'https://github.com/' + fork + '.git', 'HEAD:refs/heads/' + branch, cwd=checkout)
        body = work / 'pr-body.md'
        body.write_text('Submit **' + manifest['name'] + '** ' + manifest['version'] + ' for review.\n\n' +
                        manifest['description'] + '\n\nSource: https://github.com/' + repo +
                        '\nRelease: ' + release_url + '\nZIP: ' + asset + '\n\n' +
                        'Status: pending. Submitted through Community Store; no automatic approval or merge.\n' +
                        'Archive paths, size, manifest and declared entry points validated locally.\n' +
                        'Dependencies: ' + ', '.join(entry['dependencies']) + '\nPermissions: ' + ', '.join(entry['permissions']) +
                        '\nLicense: ' + manifest.get('license', 'not specified; author review required') + '\n\n' +
                        'AngelOS ZIP SHA256: ' + digest + '\n')
        url = gh('pr', 'create', '--repo', REGISTRY, '--base', 'main', '--head', login + ':' + branch,
                 '--title', 'Add/update ' + manifest['id'] + ' ' + manifest['version'], '--body-file', str(body))
        return {'url': url, 'release': release_url, 'id': manifest['id'], 'version': manifest['version'],
                'message': 'ZIP опубликован, заявка отправлена на проверку.'}


def main(args=None):
    args = sys.argv[1:] if args is None else args
    try:
        if args == ['auth']:
            print(json.dumps({'login': account()}))
            return 0
        if len(args) != 2 or args[0] != 'publish':
            raise ValueError('Usage: publish-plugin.py auth | publish ZIP')
        state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'angelos'
        state.mkdir(parents=True, exist_ok=True)
        with (state / 'community-publish.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Публикация уже выполняется. Дождись завершения.')
            print(json.dumps(publish(args[1]), ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyError, zipfile.BadZipFile) as exc:
        print('Публикация: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
