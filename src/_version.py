"""
Build time utility to infer version.
"""

import os, pathlib, subprocess, shutil, re
from setuptools_scm import get_version as _get_scm_version


def get_version() -> str:
    """
    Infers our opinionated version.

    For simplicity, this project defines a version as:
      <major>.<minor>.<patch>[.devX]-<hash>[-dirty]
    where
    * major.minor.patch is an arbitrary tag based value.
    * The `X` in .devX, if present, represents the distance from tag.
    * hash is the git commit our HEAD is currently pointing to.
    * A '-dirty' suffix indicates uncommitted changes in our repo.

    Some examples:
      - 1.2.3+7cfbd52
      - 1.2.3.dev3+1f7670a
      - 1.2.3.dev0+1f7670a-dirty
    """

    return _opinionated_version_from(_scm_version())


def pep440_public() -> str:
    # I can't think of a more hackish thing to do!  Just because pypi.org won't take local versions
    # and there is no officially way to allow us to stick commit hashes into the package metadata,
    # we are going to slip in a log file containing the local version (which includes commit hash)
    # and we'll let wheel build that using the dynamic feature of 'summary' metadata.  haha!
    #
    # The only way we know this works is because setuptools will be invoking this function right
    # before it goes to pick up the build-descrpition.log file as configured in pyproject.toml.

    version = get_version()
    description = 'An asyncio package to interact with the Tesla JSON web service.'
    vtext = f'Version={version}  Description={description}'
    vpath = _get_root() / 'build' / 'build-description-summary.log'
    os.makedirs(vpath.parent, exist_ok=True)
    vpath.write_text(vtext)
    return version.split('+')[0]


def _get_root() -> pathlib.Path:
    for parent in pathlib.Path(__file__).parents:
        if (parent / '.git').is_dir():
            return parent
    raise FileNotFoundError('Could not locate .git directory.')


def _get_hash() -> str:
    cmd = [
        shutil.which('git'),
        '-C', _get_root(),  # f'{root}'
        'log', '-1', '--no-decorate', '--format=%h'
    ]
    kwargs = {
        'check': True,
        'text': True,
        'stdout': subprocess.PIPE,
        'stderr': subprocess.STDOUT,
    }

    return subprocess.run(cmd, **kwargs).stdout.strip()


def _scm_version() -> str:
    """
    Getting version inferred by setuptools_scm

    Ideally, the version_scheme and local_scheme would be read from pyproject.toml.  But if those
    are changed from 'python-simplified-semver' and 'dirty-tag' respectively, the versioning
    mechanism of this module wouldn't work.  So, just keeping it simple.  And this is its own
    function primarly just to document this point.
    changed, it breaks the logic.  So, just keeping it simple.
    """

    vargs = {
        'root': _get_root(),
        'version_scheme': 'python-simplified-semver',
        'local_scheme': 'dirty-tag',
    }
    return _get_scm_version(**vargs)


def _opinionated_version_from(val: str, *, hash: str = _get_hash()) -> str:
    """
    Returns the opinionated version of the value given to us.
    """

    assert re.match(r'[a-f0-9]', hash), hash
    assert 7 <= len(hash) <= 40, f'len={len(hash)} should be between 7 and 40 (inclusive)'

    match = re.match(r'(?P<base>\d+\.\d+\.\d+)(\.dev(?P<dval>\d+)+)?(?P<dirty>\+dirty)?', val)
    ver = match.group('base')

    if any(match.group(item) for item in ('dval', 'dirty')):
        dval = '0' if match.group('dirty') else match.group('dval')
        ver += f'.dev{dval}'
    ver += f'+{hash}'

    if match.group('dirty'):
        ver += '-dirty'

    return ver


if __name__ == '__main__':
    hash = _get_hash()
    print(f'hash:    {hash}')
    print(f'scm_ver: {_scm_version()}')
    print(f'pep440:  {pep440_public()}')
    print(f'version: {get_version()}')

    samples = {
        '1.2.3': f'1.2.3+{hash}',
        '1.2.3+dirty': f'1.2.3.dev0+{hash}-dirty',
        '1.2.3.dev3': f'1.2.3.dev3+{hash}',
        '1.2.3.dev3+dirty': f'1.2.3.dev0+{hash}-dirty',
    }
    for sample, expected in samples.items():
        actual = _opinionated_version_from(val=sample, hash=hash)
        assert actual == expected, (
            'Test failed!\n'
            f'- sample   {sample!r}. \n'
            f'- expected {expected!r} \n'
            f'- actual   {actual!r}'
        )
