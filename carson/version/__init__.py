import shutil, subprocess, re, os
from os.path import isdir, join, abspath, dirname
from collections import defaultdict, namedtuple

Version = namedtuple('Version', 'major minor patch build tag hash modified')
_version = None


def get_version():
    global _version
    if _version is None:
        try:
            _version = GitStatus().version
        except GitError:
            from importlib.metadata import distribution
            return distribution(__package__).metadata['Version']

    return _version


def pep440_public():
    # I can't think of a more hackish thing to do!  Just because pypi.org won't take local versions
    # and there is no officially way to allow us to stick commit hashes into the package metadata,
    # we are going to slip in a log file containing the local version (which includes commit hash)
    # and we'll let wheel build that using the dynamic feature of 'summary' metadata.  haha!
    #
    # The only way we know this works is because setuptools will be invoking this function right
    # before it goes to pick up the build-descrpition.log file as configured in pyproject.toml.
    version = get_version()
    description = 'An asyncio package to interact with the Tesla JSON web service.'
    with open('build-description.log', 'w') as writer:
        writer.write(f'Version={version}  Description={description}')
    return version.pep440_public


class Version:
    __slots__ = ('major', 'minor', 'patch', 'build', 'tag', 'hash', 'modified', 'described')

    def __init__(self, *args):
        for index, attr in enumerate(Version.__slots__):

            setattr(self, attr, args[index])

    @property
    def pep440_public(self):
        # Because https://pypi.org/ won't take local version numbers.
        # Ref: https://peps.python.org/pep-0440/
        ver = f'{self.major}.{self.minor}.{self.patch}'
        if self.build:
            ver += f'.b{self.build}'
        if self.modified:
            ver += f'.dev0'
        return ver

    def __repr__(self, *__slots__):
        attrs = ['major', 'minor', 'patch', 'hash']
        if self.build:
            attrs.insert(-1, 'build')
        if self.modified:
            attrs.append('modified')
        attrs = ' '.join(f'{attr}={getattr(self, attr)!r}' for attr in attrs)
        return f'Version({attrs})'

    def __str__(self):
        ver = f'{self.major}.{self.minor}.{self.patch}+'
        if self.build:
            ver += f'b{self.build}-'
        ver += self.hash
        if self.modified:
            ver += '-unsupported'
        return ver


class GitStatus:

    GIT = shutil.which('git')

    COMMANDS = {
        'branch': ('branch', '--show-current'),

        # --long    Always output the tag, the number of commits, and the commit name.
        # --always  Show uniquely abbreviated commit object as fallback
        'described': ('describe', '--always', '--long', '--tags', '--dirty'),

        # An empty string here means we have local commits that aren't pushed.
        'pushed': ('branch', '--remotes', '--verbose', '--points-at', 'HEAD'),

        'head': ('log', '-1', '--format=%H'),
        'tree': ('log', '-1', '--format=%T'),
        'origin': ('remote', 'get-url', 'origin'),

        'status': ('status', '--porcelain', '--untracked-files=all', '--ignored=no'),
    }

    __slots__ = ('_cache', '_root')

    def __init__(self):
        self._cache = {}
        self._root = dirname(abspath(__file__))

    def __str__(self):
        parts = [f'{attr}={getattr(self, attr)!r}' for attr in 'owner repo'.split()]
        danger = self.danger
        if danger:
            parts.insert(0, 'UNSUPPORTED')
            parts.append(f'reason={", ".join(danger)}')
        return f'GitStatus({" ".join(parts)})'

    def validate(self):
        """
        By virtue of getting the status on the repo we're validating we can at least run commands.
        If not, the underlying getattrs will raise an exception, likely from git in the sense
        we are not in a known repository.
        """
        self.head, self.tree, self.status

    @property
    def version(self):
        desc = getattr(self, 'described')

        if desc.count('-') in (0, 1):
            raise Exception(f'No tags found? {desc!r}')

        desc_pattern = r'^[a-zA-Z]*(?P<tag>\d+\.\d+\.\d+)-(?P<build>\d+)-g(?P<hash>[a-f0-9]+)(?P<dirty>-dirty)?$'
        match = re.match(desc_pattern, desc)
        if not match:
            raise Exception(f'Unable to determine tag/version from described {desc!r}')

        tag = match.group('tag')
        major, minor, patch = [int(part) for part in tag.split('.')]
        modified = bool(match.group('dirty'))

        if match.group('build') != '0' or modified:
            patch += 1

        build = int(match.group("build")) if match.group('build') != '0' else 0
        if build == 0 and modified:
            build = 1

        hash = match.group("hash")
        return Version(major, minor, patch, build, tag, hash, modified, desc)

    @property
    def remote(self):
        ssh_pattern = r'^git@(?P<netloc>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^.]+)\.git$'
        origin = self.origin
        match = re.match(ssh_pattern, origin)
        return origin if match else None

    @property
    def owner(self):
        ssh_pattern = r'^git@(?P<netloc>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^.]+)\.git$'
        origin = self.origin
        match = re.match(ssh_pattern, origin)
        return match.group('owner') if match else None

    @property
    def repo(self):
        ssh_pattern = r'^git@(?P<netloc>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^.]+)\.git$'
        origin = self.origin
        match = re.match(ssh_pattern, origin)
        return match.group('repo') if match else None

    @property
    def modified(self):
        items = defaultdict(list)
        for item in self.status.split('\n'):
            if not item:
                continue
            indicator, path = item.split(None, 1)
            items[indicator].append(path)
        return {key: val for key, val in items.items()}

    @property
    def untracked(self):
        return self.modified.get('??')

    @property
    def dirty(self):
        return bool(self.modified)

    @property
    def danger(self):
        reasons = []
        if self.dirty:
            reasons.append('dirty')
        if self.untracked:
            reasons.append('untracked')
        if not self.pushed:
            reasons.append('unpushed')
        if not self.branch:
            reasons.append('detached')
        return reasons

    def __getattribute__(self, name):
        if name == '_cache':
            return super().__getattribute__(name)

        cache = self._cache
        if name in cache:
            return cache[name]

        if name in GitStatus.COMMANDS:
            if name not in cache:
                cache[name] = GitStatus.exec(*GitStatus.COMMANDS[name])
            return cache[name]

        return super().__getattribute__(name)

    @classmethod
    def is_git_repo(cls, path=None):
        path = path if isinstance(path, str) and path else os.getcwd()
        path = abspath(path)
        for _ in range(10):
            if isdir(join(path, '.git')):
                return True
            path = dirname(path)
        return False

    @classmethod
    def exec(cls, *args, **kwargs):
        return cls._get_output([cls.GIT] + list(args), **kwargs)

    @classmethod
    def _get_output(cls, *args, **kwargs):
        defaults = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'text': True
        }
        defaults.update(kwargs)
        with subprocess.Popen(*args, **defaults) as proc:
            buf = ''.join(line for line in proc.stdout).strip()
            proc.wait()
            if proc.returncode:
                raise GitError(f'{buf} Code: {proc.returncode}'.strip())
            return buf


class GitError(Exception):
    pass
