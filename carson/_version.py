
"""
Determines what version should be given based on environment.
"""

import re
import shutil

from os.path import join, abspath, dirname, isdir
from subprocess import run, PIPE, STDOUT

_cachedv = None

def get_version():
    global _cachedv

    if _cachedv is not None:
        return _cachedv

    try:
        described = _describe_repo()
        match = Version.RE_DESCRIBE.match(described or _get_contingency())
        if match:
            v = Version()
            v.hash = match.group('hash')
            v.tag = match.group('tag')
            v.commits = int(match.group('commits'))
            v.dirty = bool(match.group('dirty'))
            v.described = described
            _cachedv = v
    except:
        _cachedv = None

    if not isinstance(_cachedv, Version):
        _cachedv = Version()

    return _cachedv


class Version:
    RE_TAG = re.compile(r'^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$')
    RE_DESCRIBE = re.compile(r'^(?P<tag>\d+\.\d+\.\d+)-(?P<commits>\d+)-g?(?P<hash>[0-9a-f]{5,40})(?P<dirty>-dirty)?$')
    def __init__(self):
        self.hash = 'N/A'
        self.tag = '0.0.0'
        self.commits = 0
        self.dirty = False
        self.described = ''

    @property
    def major(self):
        return int(self.tag.split('.', 1)[0])

    @property
    def minor(self):
        return int(self.tag.split('.', 2)[1])

    @property
    def patch(self):
        return int(self.tag.split('.')[-1])

    @property
    def pipversion(self):
        return self.version.split('-')[0]

    @property
    def version(self):
        patch = self.patch
        commits = self.commits
        if self.dirty:
            commits += 1
        if commits:
            patch += 1
        buf = f'{self.major}.{self.minor}.{patch}'
        if commits:
            buf += f'-b{commits}'
        buf += f'-{self.hash}'
        if self.dirty:
            buf += '-unsupported'

        return buf

    def __str__(self):
        return self.version

    def __repr__(self):
        buf = f'Version({self.version} '
        if self.dirty:
            buf += 'DIRTY '
        buf += f'tag={self.tag} commits={self.commits} hash={self.hash}'
        if self.described:
            buf += f' described={self.described!r}'
        buf += ')'
        return buf

def _describe_repo():

    # 1.  Do we have git?
    git = shutil.which('git')
    if not git:
        return None

    # 2.  Are we in a git repo?
    repo_root = _get_root()
    if not repo_root:
        return None

    # 3.  Do we have a fetch URL?
    fetch_url = _get_remote(repo_root)
    if not fetch_url:
        return None

    # 4.  Is our fetch remote github?
    if 'github.com:mloyd/carson.git' not in fetch_url:
        return None

    # 5.  Finally describe the repo
    cmd = (
        git, '-C', repo_root,
        'describe', '--tags', '--dirty', '--long'
    )
    described = _get_output(*cmd).strip()
    if not described.endswith('-dirty'):
        cmd = (
            git, '-C', repo_root,
            'ls-files', '--others', '--exclude-standard'
        )
        if _get_output(*cmd).strip():
            described += '-dirty'

    return described


def _get_contingency():
    try:
        with open(join(dirname(abspath(__file__)), '__v')) as reader:
            return reader.read()
    except:
        pass

def _get_root():
    repo_root = dirname(abspath(__file__))

    for _ in range(3):
        # It should take us no more than three looks upward to find root if we're in the
        # root we're looking for.  We could be in a virtual env which doesn't count.
        if isdir(join(repo_root, '.git')):
            return repo_root
        repo_root = dirname(repo_root)

    return None


def _get_remote(repo_root):
    try:
        cmd = (
            shutil.which('git'),
            '-C', repo_root,
            'remote', 'get-url', 'origin'
        )
        return _get_output(*cmd)
    except:
        pass


def _get_output(*cmd):
    try:
        proc = run(cmd, stdout=PIPE, stderr=STDOUT)
        proc.check_returncode()
        return proc.stdout.decode(errors='replace')
    except FileNotFoundError:
        return ''
