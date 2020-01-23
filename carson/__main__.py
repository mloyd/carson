
import argparse
import asyncio
from datetime import datetime, timedelta
from . import logging, Session, VehicleStateError, TeslaSessionError


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
    except KeyboardInterrupt:
        pass


async def start(args):

    session = Session(email=args.email, password=args.password, access_token=args.access_token, verbose=args.verbose)

    try:
        if args.list:
            carnbr = 0
            for carnbr, car in enumerate(await session.vehicles()):
                carnbr += 1
                logging.info('Car #%d %r', carnbr, car)
            if not carnbr:
                logging.error('No cars associated with this account!')
            return

        car = await session.vehicles(args.name) if args.name else await session.car
        if not car:
            logging.error('No cars associated with this account!')
            return

        if car.state != 'online' and args.wake:
            logging.debug('Waking up car...')
            await car.wake_up()

        if args.stream:
            return await start_streaming(car, args.wake)

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


async def start_streaming(car, wake):
    logging.info('Press Ctrl+C to stop')
    if car.state != 'online' and wake:
        try:
            logging.info('Waking up car.')
            await car.wake_up()
        except VehicleStateError as err:
            logging.error('Could not wake up the car! %s', err, exc_info=True)
            return

    sleep_period = 30.0
    # The base amount of time to sleep each iteration.

    max_sleep = timedelta(minutes=15).total_seconds()

    iterations = 0
    waypoints = 0
    state = car.state
    user_present = False
    is_charging = False

    sleep_multiplier = 1
    # If the car is online, but there is no user (a.k.a driver) present, this multiplier will slowly
    # increase so we don't artifically keep the car awake.  I think the period let it sleep is
    # around ten minutes.

    if state == 'online':
        logging.debug('Car is online.  Getting initial data...')
        await car.data()
        user_present = car.vehicle_state.is_user_present
        is_charging = car.is_charging

    while True:
        data_points = None
        if not user_present:
            msg = 'Car is charging.' if is_charging else 'No user present.'
            logging.debug('Console stream pass.  %s', msg)
            if is_charging:
                logging.debug('%r', car)
        else:
            iterations += 1
            sleep_multiplier = 1
            logging.info(f'Console stream loop #{iterations:,}')
            try:
                data_points = await car.stream()
                if data_points:
                    sleep_multiplier = 1
                    logging.info(f'Iteration #{iterations:,} complete.  Collected {data_points:,} data points.')
            except asyncio.exceptions.CancelledError:
                logging.debug('Console stream loop cancelled.')
                break
            except Exception:
                logging.error('Unhandled error trying to stream.', exc_info=True)

        sleep = min(max_sleep, sleep_period * sleep_multiplier)
        sdelta = timedelta(seconds=sleep)
        logging.info('Console stream loop sleeping. car=%r sleep=%s (%s)', state, sdelta, datetime.now() + sdelta)
        await car.close()
        await asyncio.sleep(sleep)

        try:
            await car.refresh()
            new_state = car.state
            if new_state != state:
                logging.info('Car transitioned from %r to %r.', state, new_state)
            state = new_state

            if state == 'online':
                # Check to see if the user/driver is present.
                await car.data()
                user_present = car.vehicle_state.is_user_present
                is_charging = car.is_charging
                if not user_present and not is_charging:
                    sleep_multiplier *= 2
            else:
                sleep_multiplier = 1
                user_present = False
        except TeslaSessionError:
            logging.error('Error in main stream loop between iterations. Sleeping one minute.', exc_info=True)
            await asyncio.sleep(60)

    logging.info(f'Console stream loop ended.  Iterations={iterations:,} waypoints={waypoints:,}')


if __name__ == '__main__':
    main()
