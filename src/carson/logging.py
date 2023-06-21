
import sys
import os
import logging
import shutil
import inspect

from . import config

logger = logging.getLogger('carson')
_init = None
_debug = False


def initLogging(debug=False):
    global _init, _debug

    if _init is not None:
        return
    _init = True
    _debug = debug

    formatter = logging.Formatter('{asctime} {levelname[0]} {name}  {message}', style='{')
    handlers = [logging.StreamHandler(sys.stdout)]
    ldir, lfile = config.get('log_dir'), config.get('log_file')
    if ldir and lfile:
        handlers.append(logging.FileHandler(os.path.join(ldir, lfile)))

    for handler in handlers:
        logger.addHandler(handler)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if not debug:
        basic = logging.Formatter('{message}', style='{', datefmt='%m-%d %H:%M:%S')
        handlers[0].setFormatter(basic)


def is_debug_enabled():
    return logger.isEnabledFor(logging.DEBUG)


def log(lvl, *args, **kwargs):
    msg = ''
    if args and isinstance(args[0], str):
        msg += f'{args[0]}'
        args = tuple(args[1:])
    logger.log(lvl, msg, *args, **kwargs)


def error(*args, **kwargs):
    log(logging.ERROR, *args, **kwargs)


def warning(*args, **kwargs):
    log(logging.WARNING, *args, **kwargs)


def info(*args, **kwargs):
    log(logging.INFO, *args, **kwargs)


def debug(*args, **kwargs):
    log(logging.DEBUG, *args, **kwargs)


COLS, ROWS = shutil.get_terminal_size((120, 80))
COLS -= 35
NoneType = type(None)


def logobject(obj, name=None, logger=print, multi_line_doc=False):
    debug = logger
    if hasattr(debug, 'debug'):
        debug = debug.debug

    debug(f'{"=" * 5} {name or "logobj"} {"=" * COLS * 2}'[:COLS])
    otype = type(obj)
    otname = f'{otype.__module__}.{otype.__name__}'
    debug(f'obj {otname}')
    try:
        debug(f'file: {inspect.getfile(otype)}')
    except TypeError:
        pass

    doc = (
        inspect.getdoc(otype)
        or inspect.getcomments(otype)
        or inspect.getcomments(obj)
        or 'No doc or coment'
    )
    if '\n' in doc:
        doc = '\n'.join(f'  {ln}' for ln in doc.split('\n'))
    debug(doc)

    gentle_items = {
        'aiohttp.client_reqrep.ClientResponse': ['ok']
    }

    members = [
        (attr, getattr(obj, attr))
        for attr in dir(obj)
        if not attr.startswith('__')
        and attr not in gentle_items.get(otname, [])
    ]

    gutter = max(20, max(len(attr) for attr, val in members) if members else 20)

    is_a_funcs = [
        (name[2:], func)
        for name in dir(inspect)
        if name.startswith('is')
        and (func := getattr(inspect, name))  # noqa
        and inspect.isfunction(func)          # noqa
    ]
    for attr, val in members:
        val = 'gentle' if attr in gentle_items else val
        line = f'{attr: <{gutter}}'
        val_type = type(val)
        mname = val_type.__module__
        tname = val_type.__name__ if val_type.__name__ not in ('builtin_function_or_method',) else ''
        type_desc = f'{mname}.' if mname != 'builtins' else ''
        type_desc += tname

        if val_type in (NoneType, bool, int):
            line += repr(val)
            debug(line[:COLS])
            continue

        if val_type in (str,) or type_desc in ('yarl.URL'):
            line += f'{str(val)!r}'
            debug(line[:COLS])
            continue

        isables = ', '.join(name for name, func in is_a_funcs if func(val))
        if isables:
            line += f'({isables}) '

        if type_desc not in isables:
            line += type_desc + ' '

        if isinstance(val, dict):
            line += '{'
            entries = []
            for dkey, dval in val.items():
                parts = []
                for part in (dkey, dval):
                    if isinstance(part, (NoneType, str, int)):
                        parts.append(repr(part))
                    else:
                        parts.append(type(part).__name__)
                entries.append(':'.join(parts))
            line += ', '.join(entries)
            line += '}'
        elif isinstance(val, (list, set, tuple)):
            line += '('
            line += ', '.join(
                repr(part)
                if isinstance(part, (NoneType, str, int))
                else type(part).__name__
                for part in val
            )
            line += ')'
        else:
            doc = (
                inspect.getdoc(val)
                or inspect.getcomments(val)
                or ''
            ).strip()
            if doc:
                doc = doc.split('\n')
                line += ': ' + doc[0]
                doc = doc[1:] if multi_line_doc else []
                while doc:
                    if line[:COLS].strip():
                        debug(line[:COLS])
                    line = f'{" ": <{gutter}}' + doc[0]
                    doc = doc[1:]

        debug(line[:COLS])

    debug(f'{"=" * 50}')
