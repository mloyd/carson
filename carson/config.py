"""
Configuration is used as the default for most information.  It can, of course,
be overwritten at the object level as the API is used.
"""

import os, configparser


_config = configparser.ConfigParser()
# The cached configuration

_path = None
# When config is loaded from disk, this will store the path so updates will be
# written automatically.

_config['DEFAULT'] = {
    'email': '',
    # nikola@tesla.com

    'password': '',
    #

    'access_token': '',
    # 0a1b2c3d4e5f0a1b2c3d4e5f0a1b2c3d4e5f0a1b2c3d4e5f0a1b2c3d4e5f0a1b

    'created_at': '',
    # 1573144032

    'expires_in': '',
    # 3888000

    # 'log_dir': '',
    # 'log_file': 'carson.log'
}


def get(key, default=None):

    envvar = f'CARSON_{key.upper()}'
    if envvar in os.environ:
        return os.environ.get(envvar)

    if not _config.sections():
        load()

    val = _config['carson'].get(key, default)
    if key == 'log_dir':
        return _get_abspath(key, val or '.')

    return val


def _get_abspath(var, val):
    path = os.path.abspath(os.path.expanduser(val))
    if os.path.exists(path) and not os.path.isdir(path):
        raise ValueError(f'The configured {var} ({val!r}) exists but is not a directory.')
    elif not os.path.exists(path):
        # Make sure we at least have a valid root into which we can makedirs.
        base = os.path.dirname(path)
        tries = 0
        while os.path.dirname(base) != base:
            tries += 1
            if tries >= 10:
                raise ValueError(f'Exceeded max tries to `makedirs` for {var} ({val!r})')
            if os.path.exists(base):
                if not os.path.isdir(base):
                    raise ValueError(f'Cannot expand directories into {var}={val!r}. {base!r} is not a directory.')
                os.makedirs(path)
                return path
            base = os.path.dirname(base)
    return path


def getint(key, default=None):
    if not _config.sections():
        load()
    val = default
    try:
        val = _config['carson'].getint(key, default)
    except ValueError:
        pass
    return val


def set(key, val):
    if not _config.sections():
        load()
    _config['carson'][key] = str(val) if val is not None else ''
    _write()


def setitems(items):
    """
    Takes a dict `items` and writes its key/val to the config.
    """
    for key, val in items.items():
        set(key, val)


def save(location=None):
    global _path
    _path = location or _path or os.path.expanduser('~/.carson')
    _write()


def _write():
    if not _path:
        return

    with open(_path, 'w') as writer:
        _config.write(writer)


def load(file=None):
    """
    Tries to load configuration automatically.  It first looks for environment
    variables, then looks for config files from the default location (~/.carson).
    """

    default_files = [
        os.path.expanduser('~/.carson'),
        os.path.expanduser('~/carson.ini')
    ]
    while not file and default_files:
        file = default_files.pop(0)
        if os.path.exists(file):
            break
        file = None

    if file and os.path.exists(file):
        global _path
        _path = file
        _config.read(file)

    if 'carson' not in _config.sections():
        _config['carson'] = {}
        _write()


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        print(f'tmp={tmp!r}')
        testfile = os.path.join(tmp, 'test.txt')
        with open(testfile, 'w') as fd:
            fd.write('testing')
        checkvals = []
        checkvals.append(('~/', os.path.abspath(os.path.expanduser('~/'))))
        checkvals.append((os.path.join(testfile, 'testdir1', 'testdir2'), ValueError))
        verylong = tmp
        for i in range(20):
            verylong = os.path.join(verylong, f'subdir{i}')
        checkvals.append((verylong, ValueError))

        for trying, shouldbe in checkvals:
            result = None
            try:
                result = _get_abspath('testing', trying)
            except ValueError:
                result = ValueError
            assert result == shouldbe, f'Tried {trying!r} which should have resulted in {shouldbe!r} but instead got {result!r}'
            print(f'Passed: {trying!r} resulted in {shouldbe!r}')
