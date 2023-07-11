import sys
import os
import argparse
import asyncio
import warnings

from carson import Session, logging
from carson.tokens import TOKEN_ATTRS


def main(*args):
    if not args:
        args = sys.argv
        _arg = args[0] if args else ''
        if _arg.endswith('__main__.py') or _arg.endswith('carson'):
            args = args[1:]

    from carson import __version__
    version = f'carson/{__version__}'
    parser = argparse.ArgumentParser('carson', description=f'Command line utility for {version}')
    creds = parser.add_argument_group('Credentials')
    creds.add_argument('--token', dest='access_token', metavar='TOKEN', help='Access token to authenticate to Tesla.')
    creds.add_argument('--refresh', dest='refresh_token', metavar='TOKEN', help='Refresh token for when access token expires.')

    actions = parser.add_argument_group('Queries/Actions')
    actions.add_argument('--list', '-l', default=False, action='store_true', help='List vehicles associated with the account and exit.')
    actions.add_argument('--name', metavar='DISPLAY_NAME', help='The vehicle display name')
    actions.add_argument('--stream', '-s', default=False, action='store_true', help='Start streaming telemetry.')
    actions.add_argument('--command', default=[], metavar='CMD', action='append', help='Perform the data request or command specified.')
    actions.add_argument('--wake', dest='wake', default=False, action='store_true', help='Wake the car if necessary.')
    actions.add_argument('--no-wake', default=None, action='store_true', help=argparse.SUPPRESS)

    misc = parser.add_argument_group('Misc')
    misc.add_argument('--version', default=False, action='store_true', help='Prints version and exits')
    misc.add_argument('--verbose', '-v', default=0, action='count')
    args = parser.parse_args(args)
    logging.initLogging(debug=args.verbose)

    if args.version:
        print(version)
        raise SystemExit(0)

    args.list |= not any([args.command, args.stream, args.name])
    if args.no_wake:
        warnings.warn('The --no-wake argument is deprecated.  You can explicitly wake using the --wake argument.')
        if args.wake:
            raise SystemExit('Cannot specify both --wake and --no-wake')

    try:
        asyncio.run(start(args), debug=args.verbose)
    except KeyboardInterrupt:
        pass


async def start(args):

    kwargs = {
        'credential': {
            # Reads token attributes config in order of precedence:
            #  1) Command line argument
            #  2) Environment variable
            key: val
            for key in TOKEN_ATTRS
            if (
                val := (
                    getattr(args, key, None)
                    or os.environ.get(f'CARSON_{key.upper()}', None)
                )
            )
        },
        'verbose': args.verbose,
        'callback': _notify_token_refreshed,
    }

    async with Session(**kwargs) as session:
        if not session.access_token:
            raise SystemExit('You must provide access token or set environment variable CARSON_ACCESS_TOKEN.')
        result = await (
            session.vehicles(name=args.name)
            if args.name or args.list
            else session.car
        )
        if not result:
            raise SystemExit('Nothing associated with this account!')

        if args.list or isinstance(result, list):
            result = result if isinstance(result, list) else [result]
            for carnbr, car in enumerate(result, start=1):
                logging.info('Car #%d %r', carnbr, car)
            return

        car = result[0] if isinstance(result, list) else result
        if car.in_service:
            logging.info('%r', car)
            if args.wake or args.stream or args.command:
                logging.error('Cannot perform any more commands while car is in Tesla Service.')
            return

        if car.state != 'online' and args.wake:
            logging.debug('Waking up car...')
            await car.wake_up()

        if args.stream:
            return await car.stream()

        if car.state == 'online':
            await car.data()

        logging.info('%r', car)

        for cmd in args.command:
            if 'stream' in cmd.lower():
                continue
            func = getattr(car, cmd.lower())
            if asyncio.iscoroutinefunction(func):
                logging.info('Result of `await %s()` is %s', cmd, await func())
            elif callable(func):
                logging.info('Result of `%s()` is %s', cmd, func())
            else:
                logging.info('Result of %r is %s', cmd, func)


def _notify_token_refreshed(updates: dict):
    if not isinstance(updates, dict):
        raise TypeError(f'Expected dict, got {type(updates).__name__}')
    invalid_keys = [
        repr(f'{str(key)[:2]}***')
        for key in updates
        if not isinstance(key, str)
        or key not in TOKEN_ATTRS
    ]
    if invalid_keys:
        raise TypeError(f'Expected mapping of string keys only.  Got unknown keys {", ".join(invalid_keys)}.')
    invalid_vals = [
        f'{key}={type(val).__name__}'
        for key, val in updates.items()
        if not isinstance(val, (str, int))
    ]
    if invalid_vals:
        raise TypeError(f'Expected mapping of str --> str|int. {", ".join(invalid_vals)}')

    logging.warning('Token refreshed but not stored/logged for security reasons.')
    if logging.is_debug_enabled():
        loggable = [
            f'  {key}: val=<hidden> type={type(val).__name__} len={len(str(val)):,}'
            for key, val in updates.items()
        ]
        for ln in loggable:
            logging.warning(ln)


if __name__ == '__main__':
    raise SystemExit(main())
