
import argparse
import asyncio
import warnings

from getpass import getpass

from . import auth, logging, Session, TeslaCredentialError, get_version


def main():
    parser = argparse.ArgumentParser('carson', description=f'Command line utility for carson/{get_version()}.')
    parser.add_argument('--email', '-e', help='The email associated with your Tesla account.')
    parser.add_argument('--password', '-p', metavar='P', help=argparse.SUPPRESS)
    parser.add_argument('--access-token', '-t', '--token', help='An access token that can be used in lieue of email/password.')
    parser.add_argument('--list', '-l', default=False, action='store_true', help='List vehicles associated with the account and exit.')
    parser.add_argument('--name', '-n', '--car-name', '--car', '--display-name', help='The vehicle display name')
    parser.add_argument('--stream', '-s', default=False, action='store_true', help='Start streaming telemetry.')
    parser.add_argument('--command', '-c', default=[], action='append', help='Perform the data request or command specified.')
    parser.add_argument('--wake', dest='wake', default=False, action='store_true', help='Wake the car if necessary.')
    parser.add_argument('--no-wake', default=None, action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--version', default=False, action='store_true', help='Prints version and exits')
    parser.add_argument('--verbose', '-v', default=0, action='count')
    args = parser.parse_args()

    if args.version:
        print(f'carson-{get_version()}')
        return

    if args.no_wake:
        warnings.warn('The --no-wake argument is deprecated.  You can explicitly wake using the --wake argument.')
        if args.wake:
            raise SystemExit('Cannot specify both --wake and --no-wake')

    if not any([args.list, args.command, args.stream, args.name]):
        return parser.print_help()

    logging.initLogging(debug=args.verbose)
    try:
        asyncio.run(start(args), debug=args.verbose)
    except TeslaCredentialError as err:
        print(err, '\n')
        parser.print_help()
    except KeyboardInterrupt:
        pass


async def start(args):

    session = Session(email=args.email, password=args.password, access_token=args.access_token, verbose=args.verbose)
    if session.email and not session.password and not session.access_token:
        session.password = getpass(f'Password for {session.email}: ')
    try:

        result = await session.vehicles(name=args.name) if args.name or args.list else await session.car
        if not result:
            logging.error('Nothing associated with this account!')
            return

        if args.list or isinstance(result, list):
            result = result if isinstance(result, list) else [result,]
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

    finally:
        await session.close()


if __name__ == '__main__':
    main()
