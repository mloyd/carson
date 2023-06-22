
import sys
import logging

logger = logging.getLogger('carson')


def initLogging(debug=False):
    level = logging.INFO
    formatter = logging.Formatter('{message}', style='{', datefmt='%m-%d %H:%M:%S')
    if debug:
        formatter = logging.Formatter('{asctime} {levelname[0]} {name}  {message}', style='{')
        level = logging.DEBUG

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)

def is_debug_enabled():
    return logger.isEnabledFor(logging.DEBUG)


def log(lvl: int, *args, **kwargs):
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
