
import asyncio, re
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from aiohttp import WSMsgType

from . import logging, utils
from .core import VehicleStateError, TeslaSessionError

STREAMING_ENDPOINT = 'wss://streaming.vn.teslamotors.com/streaming/'

TOO_LONG = timedelta(seconds=60)
RE_CLIENT_ERROR = re.compile(r'client[ _]*error')
RE_DISCONNECTED = re.compile(r'vehicle[ _]*disconnected')


async def stream(car, *, callback=None):
    """
    The main entry point to streaming telemetry from the vehicle.

    callback:
      The function (awaitable or not) to call on message receive.
    """

    state = car.state
    if state != 'online':
        raise VehicleStateError('Cannot stream if car is not online.', state=state)

    if not hasattr(car, 'vehicle_state') or not car.vehicle_state.is_user_present:
        await car.data()

    iscoro = asyncio.iscoroutinefunction(callback)
    user_present = car.vehicle_state.is_user_present

    iteration = 0
    msg_count = 0
    waypoints = 0
    debug = logging.is_debug_enabled()

    vehicle_disconnects = 0
    # Just to keep a count of how many disconnects we get.

    timeouts = 0
    # Count of how many times we timed out.  Happens normally when car is idle at stoplight.

    last_known_shift_state = None
    # Tesla returns an empty string when the car is turned off.  Otherwise it returns:
    #   D=drive R=reverse P=park N=neutral

    # `cols` will be the payload list/order in which we want the data.  We don't send `timestamp` in
    # the outbound payload.  But we have here because it does come back in each data:update record.
    # We act on the `shift_state` value so we need to save the index of its location.
    cols = list(STREAM_COLUMNS.keys())

    while user_present:
        iteration += 1
        logging.info('Starting stream loop #%d. %s', iteration, car)

        reader = None
        subscribe = f'{{"msg_type":"data:subscribe_oauth","token":"{car.access_token}","value":"{",".join(cols[1:])}","tag":"{car.vehicle_id}"}}'
        logging.debug('subscribe=%r', subscribe)

        try:
            reader = await car.ws_connect(STREAMING_ENDPOINT, receive_timeout=10.0)

            # Upon connection, Tesla will wait for us to send a 'subscribe' message to initiate the
            # telemetry streaming.
            await reader.send_str(subscribe)

            # The first `msg` we receive after sending the subscribe will be a `hello`.
            # Example: {'msg_type': 'control:hello', 'connection_timeout': 0}
            msg = await next_message(reader)
            if not msg:
                raise TeslaSessionError('Streaming Error! Did not get first message after subscribe!')

            mtype, etype = msg.get('msg_type', None), msg.get('error_type', None)
            if etype or mtype != 'control:hello':
                logging.error('Expected msg_type="control:hello" but got %r', msg)
                raise TeslaSessionError(f'Streaming Error! Expected "control:hello" but got {msg!r}')

            while True:
                msg = await next_message(reader)
                if msg is None:
                    break
                _ensure_attrs(msg)

                # We should have a dict parsed from json at this point.  Examples:
                #   {"msg_type":"control:hello","connection_timeout":0}
                #   {"msg_type":"data:update","tag":"1234567890","value":"1573135344345,,14932.8,54,236,185,32.747871,-97.092712,0,,163,136,185"}
                #   {"msg_type":"data:error","tag":"1234567890","value":"disconnected","error_type":"vehicle_disconnected"}
                #   {"msg_type":"data:error","tag":"1234567890","value":"Can't validate password. ","error_type":"client_error"}
                #
                # Or we have one represented by a timeout
                #   {"msg_type":"data:error","error_type":"timeout"}
                #
                mtype, etype = msg['msg_type'], msg.get('error_type', None)

                if etype or mtype != 'data:update':
                    etype = str(etype)
                    # If the error_type is vehicle_disconnected... that's normal.  Anything else
                    # should raise an exception.  Sometimes a disconnect happens when sitting at
                    # a red light.
                    if RE_DISCONNECTED.search(etype):
                        vehicle_disconnects += 1
                        logging.info('Disconnected. timeouts=%d disconnects=%d msg_count=%d waypoints=%d msg=%r', timeouts, vehicle_disconnects, msg_count, waypoints, msg)
                        break

                    if etype == 'timeout':
                        # Not uncommon.  May just be at a stoplight.
                        timeouts += 1
                        logging.info('Timeout. timeouts=%d disconnects=%d msg_count=%d waypoints=%d msg=%r', timeouts, vehicle_disconnects, msg_count, waypoints, msg)
                        break

                    else:
                        logging.warning('msg_count=%d waypoints=%d msg=%r', msg_count, waypoints, msg)
                        raise TeslaSessionError(f'Streaming Error! {msg!r}')
                else:
                    msg_count += 1

                func = logging.debug if debug or callback else logging.info
                func('Message %d %r', msg_count, msg)

                tag = int(msg['tag'])
                if tag != car.vehicle_id:
                    error = f'Streaming Error! The telemetry tag ({tag!r}) does not match the expected car ID ({car.vehicle_id!r}).'
                    logging.error(error)
                    raise TeslaSessionError(error)

                waypoint = Waypoint(msg['value'], cols, tag)
                shift_state = waypoint.shift_state
                if shift_state != last_known_shift_state:
                    logging.info('New shift state %r.  Last shift state %r', shift_state, last_known_shift_state)
                last_known_shift_state = shift_state
                if shift_state:
                    waypoints += 1

                if callback:
                    if iscoro:
                        asyncio.create_task(callback(waypoint))
                    else:
                        callback(waypoint)

        except asyncio.exceptions.CancelledError:
            logging.info('Streaming cancelled.  msg_count=%d waypoints=%d.', msg_count, waypoints)
            raise
        except Exception as err:
            logging.error('Streaming aborted due to unhandled error. %s', err, exc_info=True)
            raise
        finally:
            if reader:
                await reader.close()

        await car.refresh()
        new_state = car.state
        if new_state != state:
            logging.info('Car transitioned from %r to %r during stream loop.', state, new_state)

        state = car.state
        if state != 'online':
            user_present = False
        else:
            await car.data()
            user_present = car.vehicle_state.is_user_present

    logging.info('Streamer task ending. car=%r. user_present=%s shift_state=%r waypoints=%d', car.state, user_present, last_known_shift_state, waypoints)
    return waypoints


async def next_message(reader):
    """
    Returns a dict from a JSON decoded message received from the websocket `reader`.
    """
    data = {'msg_type': 'data:error', 'error_type': 'timeout'}
    try:
        msg = await reader.receive()
        if not msg:
            logging.warning('Received no data while waiting for next message.')
            return None
        elif msg.type == WSMsgType.CLOSED:
            return None
        elif msg.type != WSMsgType.BINARY:
            logging.error('Expecting WSMsgType.BINARY but got %r.', msg)
            return None
        else:
            data = utils.json_loads(msg.data.decode())
    except asyncio.exceptions.TimeoutError:
        logging.debug('Timeout waiting for next message.')
    except Exception as err:
        logging.error('Unknown error while waiting for next message: %s', err, exc_info=True)
        if logging.is_debug_enabled():
            logging.logobject(err)
        raise

    return data


MSG_TYPES = {
    'control:hello': (set(['msg_type', 'connection_timeout']), set()),
    'data:update': (set(['msg_type', 'tag', 'value']), set()),
    'data:error': (set(['msg_type', 'error_type']), set(['tag', 'value']))
}


def _ensure_attrs(msg):
    """
    This is more of a debugging and asserting function.  Meaning exceptions will be raised when
    running in development mode.  But only non-disruptive message are generated when running in
    optimized mode (a.k.a production).
    """

    if not isinstance(msg, dict):
        logging.error('Expected a dict but got %s. %r', type(msg), msg)
        assert False
        return

    # Each message should have at least a message type (msg_type).  Subsequently, the attributes
    # expected depend on the value of `msg_type`.  This is a mapping from the message type to
    # a list of required other attributes and a list (optionally) of optional attributes.

    if 'msg_type' not in msg:
        logging.error('Unknown message.  Does not have `msg_type`. %r', msg)
        assert False
        return

    expected, optional = MSG_TYPES.get(msg['msg_type'], (set(), set()))
    missing = [attr for attr in expected if attr not in msg]
    extra = set([attr for attr in msg if attr not in expected])
    extra.difference_update(optional)

    if extra:
        extra_vals = ', '.join(f'{attr!r}={msg.get(attr)!r}' for attr in extra)
        logging.warning('Ignoring unknown attributes in websocket response %s', extra_vals)

    if missing:
        log_msg = 'Missing required attributes in websocket response! {}'.format(', '.join(missing))
        logging.warning(log_msg)

    assert not missing and not extra


async def _manual_data_point(car, cols):
    """
    When the streaming websocket is not responding, we might need to step in and get a data point by polling the current
    status of the car.
    """
    await car.refresh()
    if car.state != 'online':
        raise VehicleStateError(state=car.state)
    await car.data()

    args = {
        'timestamp': int(car.drive_state.timestamp.timestamp() * 1000),
        'speed': car.drive_state.speed if car.drive_state.speed is not None else '',
        'odometer': car.vehicle_state.odometer,
        'soc': car.charge_state.battery_level,
        'elevation': '',  # TODO: Why can we not poll the current elevation?  Is it only available via streaming?
        'est_heading': car.drive_state.heading,
        'est_lat': car.drive_state.latitude,
        'est_lng': car.drive_state.longitude,
        'power': car.drive_state.power,
        'shift_state': car.drive_state.shift_state if car.drive_state.shift_state is not None else '',
        'range': car.charge_state.ideal_battery_range,
        'est_range': car.charge_state.est_battery_range,
        'heading': car.drive_state.heading
    }

    msg = {
        'msg_type': 'data:update',
        'tag': car.vehicle_id,
        'value': ','.join(f'{{{c}}}' for c in cols).format(**args)
    }
    logging.debug('Manual data point %r', msg)
    return msg


class Waypoint:
    """
    Utility class representing a single waypoint received from Tesla's streaming endpoint.

    Since it is input data from and external system, it provides a basic level of validation of the
    data it accepts.
    """

    def __init__(self, record, cols, tag):
        """
        record: A CSV string of data representing the record.
        cols: A list of column names to which the record fields map.
        tag: Since tag is not a part of the CSV record, it is supplied separately.
        """

        if not isinstance(cols, list) or not all(cols):
            raise ValueError('Value for `cols` must be list of strings.')

        if not isinstance(record, str) or not record:
            raise ValueError('Value for `record` must be csv string.')

        self._cols = cols
        self._record = record
        self._fields = record.split(',')
        self.tag = tag

        if len(self._cols) > len(self._fields):
            raise ValueError(f'Not enough values in record ({len(self._fields)}) to match all {len(self._cols)} columns.')
        elif len(self._cols) < len(self._fields):
            raise ValueError(f'Too many values in record ({len(self._fields)}) for {len(self._cols)} column(s).')

        if __debug__:
            self._cols = []
            for col in cols:
                if not isinstance(col, str):
                    raise ValueError(f'Each element in `cols` should be a `str`. Not {type(col)!r}.')
                if col != col.lower():
                    raise ValueError('Column names should be passed in as all lowercase.')
                if not col:
                    raise ValueError('Every element in cols must evaluate to a non-empty string.')
                if col in self._cols:
                    raise ValueError(f'Duplicate column name {col!r}')
                self._cols.append(col)

        self._map_col_to_parser = {
            'timestamp':   (Waypoint._parse_timestamp,             ),  # noqa
            'speed':       (Waypoint._parse_int,           0       ),  # noqa
            'odometer':    (Waypoint._parse_float,         0       ),  # noqa
            'soc':         (Waypoint._parse_int,           0,   100),  # noqa
            'elevation':   (Waypoint._parse_int,      -6_500,      ),  # noqa
            'est_heading': (Waypoint._parse_int,           0,   360),  # noqa
            'heading':     (Waypoint._parse_int,           0,   360),  # noqa
            'est_lat':     (Waypoint._parse_float,     -90.0,  90.0),  # noqa
            'est_lng':     (Waypoint._parse_float,    -180.0, 180.0),  # noqa
            'power':       (Waypoint._parse_int,                   ),  # noqa
            'range':       (Waypoint._parse_int,                   ),  # noqa
            'est_range':   (Waypoint._parse_int,                   ),  # noqa
        }

        # By simply call getattributes we essentially are validating initial values.
        [getattr(self, attr) for attr in self._cols]

    @property
    def record(self):
        return self._record

    @staticmethod
    def _parse_numeric(func, val, minimum=None, maximum=None):
        if not val:
            return None
        val = func(val)
        if minimum is not None and val < minimum:
            raise ValueError(f'Value {val} is less than minimum ({minimum})')
        if maximum is not None and val > maximum:
            raise ValueError(f'Value {val} is greater than maximum ({maximum})')
        return val

    @staticmethod
    def _parse_float(val, minimum=None, maximum=None):
        return Waypoint._parse_numeric(float, val, minimum, maximum)

    @staticmethod
    def _parse_int(val, minimum=None, maximum=None):
        fval = Waypoint._parse_numeric(float, val, minimum, maximum)
        return int(fval) if fval is not None else fval

    @staticmethod
    def _parse_str(val, *args):
        if isinstance(val, str):
            val = val.strip()
        if val:
            return val
        return None

    @staticmethod
    def _parse_timestamp(val, minimum=None, maximum=None):
        val = Waypoint._parse_int(val)
        if val > 9_999_999_999:
            val *= .001
        ts = datetime.fromtimestamp(val, tz=timezone.utc)
        if minimum is not None and ts < minimum:
            raise ValueError('Value {ts} is less than minimum ({minimum})')
        if maximum is not None and ts > minimum:
            raise ValueError(f'Value {ts} is greater than maximum ({maximum})')
        return ts

    def __getitem__(self, attr, default=None):
        if attr in self._cols:
            return getattr(self, attr)
        return default

    def __getattribute__(self, attr):
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            if attr.startswith('_'):
                raise

        try:
            idx = self._cols.index(attr.lower())
        except ValueError:
            return 'I don\'t have that.'

        parser, *args = self._map_col_to_parser.get(attr, (self._parse_str,))
        val = self._fields[idx]
        try:
            return parser(val, *args)
        except ValueError as err:
            raise ValueError(f'Could not parse {attr!r}.  {err}')

    def __repr__(self):
        buf = []
        for i, col in enumerate(self._cols):
            buf.append(f'{col}={self._fields[i]!r}')
        return f'Waypoint({" ".join(buf)})'

    def __str__(self):
        buf = []
        for col in self._cols:
            buf.append(f'{col}={getattr(self, col)!r}')
        return f'Waypoint({" ".join(buf)})'

    def dump(self):
        """
        Returns a dict of itself that can be used by `utils.json_dumps`.   It cannot be used
        directly by Python's `json.dumps` because timestamp will be an instance of `datetime`.
        """
        result = {'tag': self.tag}
        result.update({col: getattr(self, col) for col in self._cols})
        return result

    def encode(self, encoding='utf-8', errors='strict'):
        """
        Returns original record encoded as bytes.  Useful for stream processing (e.g. Kafka).
        """
        return self.record.encode(encoding=encoding, errors=errors)


STREAM_COLUMNS = {
    'timestamp': 'timestamp',
    # Timestamp given by Tesla.

    'speed': 'integer',
    # Speed expressed in miles per hour.

    'odometer': 'real',
    # Number of miles on the odometer.

    'soc': 'integer',
    # State of charge - battery percentage charged

    'elevation': 'integer',
    # Elevation of the car expressed in feet

    'est_heading': 'integer',
    # This is the proper navigational 'heading' or 'Yaw' which is the direction the car is pointed.

    'est_lat': 'real',
    # Approximate latitude in decimal notation.

    'est_lng': 'real',
    # Approximate longitude in decimal notation.

    'power': 'integer',
    'shift_state': 'string',
    'range': 'integer',
    'est_range': 'integer',

    'heading': 'integer',
    # In contrast, the term 'heading' here refers to navigational term 'course' meaning the direction the car is
    # actually travelling.  This value represents the last course when the car was in motion.
    #
    # Example est_heading/heading: 185/357
    # I back in to my garage because of where my charger is located.  So its nose is looking nearly due-south.  But the
    # heading (a.k.a course) is nearly due north because my speed was backing in.
}
