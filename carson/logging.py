
import sys
import os
import logging

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
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.get('log_dir'), config.get('log_file')))
    ]
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


def logobject(obj, name='obj', everything=False, width=120, limit=320):
    logDivider('-', half=True)
    logger.info(f'_logobject(name={name} type={obj.__class__.__module__}.{obj.__class__.__name__})')
    logDivider('-', half=True)
    printedSomething = False
    for attr in dir(obj):
        if not everything and attr.startswith('_'):
            continue
        printedSomething = True
        try:
            attrstr = f'{getattr(obj, attr)!r}'.replace('\n', '\\n')
        except Exception as otherError:
            attrstr = f'otherError = {otherError!r}'
        if len(attrstr) > limit:
            attrstr = f'{attrstr[:limit - 3]}...'

        extra = ''
        if len(attrstr) > width:
            extra = attrstr[width:]
            attrstr = attrstr[:width]
        logger.info(f'{attr: <20}  {attrstr}')
        while extra:
            attr = ''
            logger.info(f'{attr: <20}  {extra[:width]}')
            if len(extra) > width:
                extra = extra[width:]
            else:
                extra = ''
    if not printedSomething:
        logger.info(f'Nothing to log for {name}.')
    logger.info(f'end of _logobject')


_divider_width = None
def logDivider(divider='=', half=False):  # noqa E302
    global _divider_width
    if _divider_width is None:
        try:
            # Try to find a console StreamHandler in the logger handlers.  If found, get its formatter and find the prefix length
            handlers = sorted(logger.handlers, key=lambda h: hasattr(h, 'stream') and hasattr(h.stream, 'name') and ('stdout' in h.stream.name or 'stderr' in h.stream.name))
            formatter = handlers[0].formatter
            prefix = formatter.format(logging.LogRecord(name=logger.name, level=logging.INFO, pathname='', lineno=1234, msg='', args=[], exc_info=None))

            # Calling get_terminal_size on redirected output may raise OSError.  Regardless
            # of what it may raise, just pass on it and use something default.
            _divider_width = os.get_terminal_size().columns

            # Subtract the length of the prefix from the console column width
            _divider_width -= len(prefix)
        except:  # noqa E722
            _divider_width = 200

    logger.info(divider * (int(_divider_width * .5) if half else _divider_width))
