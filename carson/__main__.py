
import argparse
import asyncio
from getpass import getpass

from . import logging, Session, TeslaCredentialError


def main():
    parser = argparse.ArgumentParser('carson', description='Command line utilility for carson.')
    parser.add_argument('--email', '-e', help='The email address associated with your Tesla account.')
    parser.add_argument('--password', '-p', help='The password associated with your Tesla account.')
    parser.add_argument('--access-token', '-t', '--token', help='An access token that can be used in lieue of email/password.')
    parser.add_argument('--list', '-l', default=False, action='store_true', help='List vehicles associated with the account and exit.')
    parser.add_argument('--name', '-n', '--car-name', '--display-name', help='The vehicle display name')
    parser.add_argument('--stream', '-s', default=False, action='store_true', help='Start streaming telemetry.')
    parser.add_argument('--command', '-c', default=[], action='append', help='Perform the data request or command specified.')
    parser.add_argument('--no-wake', dest='wake', default=True, action='store_false', help='If the car is not awake, don\'t try.')
    parser.add_argument('--verbose', '-v', default=0, action='count')
    args = parser.parse_args()

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
        if args.list:
            carnbr = 0
            for carnbr, car in enumerate(await session.vehicles()):
                carnbr += 1
                logging.info('Car #%d %r', carnbr, car)
            if not carnbr:
                logging.error('No cars associated with this account!')
            return

        car = await session.vehicles(name=args.name) if args.name else await session.car
        if not car:
            logging.error('No cars associated with this account!')
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
