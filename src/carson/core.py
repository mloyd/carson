"""
The basic classes representing a connection with the Tesla web service and the
cars on your account.
"""
from typing import Any
import os
import asyncio
import configparser
import time
import warnings
from datetime import datetime, timedelta, timezone
from pprint import pformat

from aiohttp import ClientSession

from . import OWNER_BASE_URL
from . import tokens
from . import endpoints
from . import __version__ as _version

LEGACY_ATTRIBUTES = """
    [legacy]
    # These are legacy attributes and methods that may still exist and appear to
    # be functional but either return invaluable data or simply could be wrong.
    # Take these with a grain of salt. The respective hearsay or anecdote are
    # noted with each.

    option_codes
    # Apparently abandoned.  Use `vehicle_state` instead
    # https://github.com/timdorr/tesla-api/issues/168

    color
    # I've never seen the color be anything other than null

    backseat_token
    backseat_token_updated_at
    # These two, like color, have always been null for me.  I'm guessing this
    # could be wrong since I have never seen this data for anything other than
    # a Model 3.
"""
_legacy_parser = configparser.ConfigParser(allow_no_value=True)
_legacy_parser.read_string(LEGACY_ATTRIBUTES)
LEGACY_ATTRIBUTES = tuple(_legacy_parser.options('legacy'))
REQUEST_TIMEOUT = 408  # https://httpwg.org/specs/rfc9110.html#status.408


class TeslaSessionError(Exception):
    """
    Represents a generic exception raised when the expected response from the Tesla web service
    request is not as expected.
    """
    def __init__(self, jdata=None, /, **kwargs):

        assert bool(jdata) ^ bool(kwargs), f'Should not be both args and kwargs. args={jdata} kwargs={kwargs}'

        if jdata:
            kwargs = jdata

        self.timestamp = kwargs.get('carsonTimestamp', None)

        self.response = kwargs.get('response', None)
        # The JSON response returned from the Tesla endpoint.

        self.status = kwargs.get('status', 0)
        # The HTTP response status code

        # The error/desc reported back by Tesla
        self.error = kwargs.get('error', None) or f'Status {self.status}'
        self.error_description = kwargs.get('error_description', None) or 'N/A'

        super().__init__(self.error)


class Session:
    """
    Creates an HTTP client session context to Tesla given the provided access_token
    """

    def __init__(self, *, credential=None, logger=None, verbose=0, **kwargs):
        """
        credential:
            Anything that accepts __getitem__ for the usual items (a.k.a. a dict object):
              - access_token: str
              - refresh_token: str
              - expires_in: int
              - created_at: int

        NOTE: it is an error to pass both a credential and kwargs for the same items.
        """
        deprecated = {
            attr: kwargs.pop(attr)
            for attr in kwargs
            if attr in 'email password'.split()
        }
        if deprecated:
            warnings.warn('carson.Session no longer uses email/password.  Please remove.')

        if credential is None:
            credential = {
                attr: (
                    kwargs.pop(attr, None)
                    or os.environ.get(f'CARSON_{attr.upper()}', None)
                )
                for attr in tokens.TOKEN_ATTRS
            }
        else:
            doubled = [el for el in tokens.TOKEN_ATTRS if el in kwargs]
            if doubled:
                raise ValueError(f'Cannot pass both a credential object and {", ".join(doubled)}')

        self._credential = tokens.Credential(credential)

        if (callback := kwargs.pop('callback', None)):
            self._credential.add_refresh_callback(callback)

        # We should have consumed everything in kwargs by this point.
        if kwargs:
            raise TypeError(f'Unexpected keyword argument: {", ".join(kwargs)}')

        verbose = 1 if verbose is True else verbose
        self.verbose = verbose if isinstance(verbose, int) else 1
        self._logger = logger    # If you want to set your own logger
        self._vehicles = {}      # Our cached vehicles which maps name to instance of vehicle.
        self._request_count = 0  # How many outbound reqeusts have been made.
        self.timer = time.monotonic

        headers = {'User-Agent': f'carson/{_version}', 'Accept': 'application/json'}
        self._session = ClientSession(headers=headers)
        self.access_token = self._credential.access_token

    @property
    def logger(self):
        if not self._logger:
            from .logging import logger
            self._logger = logger
        return self._logger

    @property
    def access_token(self):
        return self._credential.access_token

    @access_token.setter
    def access_token(self, val: str):
        val = '' if val is None else val
        val = val.strip() if isinstance(val, str) else val
        self._credential.access_token = val
        if not val:
            self._session.headers.pop('Authorization', None)
            auth_header = self._session.headers.get('Authorization', None)
            assert auth_header is None, f'session.headers["Authorization"]=={auth_header!r}'
        else:
            self._session.headers['Authorization'] = f'Bearer {val}'

    @property
    def expires_at(self) -> datetime:
        created_at = self._credential.created_at
        expires_in = self._credential.expires_in
        if isinstance(created_at, int) and isinstance(expires_in, int):
            return (
                datetime.fromtimestamp(created_at, tz=timezone.utc)
                + timedelta(seconds=expires_in)
            )

    @property
    def expired(self) -> bool:
        expires_at = self.expires_at
        return (
            not isinstance(expires_at, datetime)
            or datetime.now(tz=timezone.utc) > expires_at
        )

    async def user(self) -> dict:
        user = getattr(self, '_user', None)
        if user is None:
            jdata = await self.request(method='GET', path='/api/1/users/me')
            self._user = jdata['response']
        return self._user

    def __str__(self):
        # buf = f'<Session email={self.email!r}'
        buf = '<Session'

        # If `self._vehicles` is empty, it doesn't mean we don't have any.  So
        # don't report zero.  But we shouldn't make a request simply to get the
        # number of vehichles either.  Unless this would not be the first
        # request.
        if self._vehicles or self._request_count:
            buf += f' vehicles={len(self._vehicles):,}'

        if self.access_token:
            # If we have an access token, show that it is expired or when it will.
            expired = self.expired
            if expired or expired is None:
                buf += ' EXPIRED'
            else:
                buf += f' expires={self.expires_at - datetime.now(tz=timezone.utc)}'

        return buf + '>'

    def __getattribute__(self, name: str):
        if name in tokens.TOKEN_ATTRS:
            _cred = super().__getattribute__('_credential')
            return getattr(_cred, name)
        return super().__getattribute__(name)

    def __setattr__(self, name: str, val: Any):
        # Even if it's a known token attribute, if we have a data descriptor for it, set
        # ourselves first.  It's assumed our own data descriptors will set the _credential too.
        if name in tokens.TOKEN_ATTRS and not hasattr(self, name):
            _cred = super().__getattribute__('_credential')
            setattr(_cred, name, val)
        else:
            super().__setattr__(name, val)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.verbose > 2:
            self.logger.debug('Session.__exit__(exc_type=%r  exc_value=%r  traceback=%r', exc_type, exc_value, traceback)
        assert not self._session or self._session.closed

    async def __aenter__(self):
        if self.verbose > 2:
            self.logger.debug('Session.__aenter__() self._session=%s', self._session)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.verbose > 2 or self.verbose and any([exc_type, exc_value, traceback]):
            self.logger.debug('Session.__aexit__(exc_type=%r  exc_value=%r  traceback=%r)', exc_type, exc_value, traceback)
        await self.close()

    def add_refresh_callback(self, callback):
        """
        If an access token is expired and is refreshed, call the 'callback' function when the
        access token is refreshed so it can be handled/saved accordingly.
        """
        return self._credential.add_refresh_callback(callback)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def vehicles(self, *, name=None, cache=True):
        """
        Returns a car matched by name or a list of vehicles owned by the Tesla
        account.

        name:
          If None, all cars are returned.

          If not None, an exact match is attempted first.  If no match is found,
          an attempt to make a case-insensitive match based on the display name
          either 'starting with' or 'ending with' is made.

        cache:
          If True (default) then return what is cached, if anything.
          If False, disregard memory and make another request to Tesla.
        """

        if not cache:
            self._vehicles.clear()

        if not name and self._vehicles:
            return self._vehicles

        if not self._vehicles:
            # curl -i -H "Authorization: Bearer d48****281" https://owner-api.teslamotors.com/api/1/vehicles
            jdata = await self.get('/api/1/vehicles')
            vehicles = [Vehicle(self, v) for v in jdata.get('response', None) or []]
            self._vehicles = {v.display_name: v for v in vehicles}

        if name:
            car = self._vehicles.get(name)
            if car:
                return car
            name = name.lower()
            for car in self._vehicles.values():
                lowered = car.display_name.lower()
                if lowered.startswith(name) or lowered.endswith(name):
                    return car

        return list(self._vehicles.values())

    @property
    async def vehicle(self):
        """
        The equivalent of "I'm Feeling Lucky".

        But seriously, my impression is Tesla returns the list of cars in
        chronological order by VIN or purchase/order date?  Returning the 'end'
        car is the most recent car (just guessing).
        """
        if not self._vehicles:
            await self.vehicles()
        if not self._vehicles:
            return None
        return list(self._vehicles.values())[-1]

    car = vehicle

    async def ws_connect(self, *args, **kwargs):
        return await self._session.ws_connect(*args, **kwargs)

    def _request_debug(self, response, response_payload, request_payload, started, stopped):
        if not self.verbose:
            return
        request = response.request_info
        if self.verbose == 1:
            ver = f'{response.version.major}.{response.version.minor}'
            ver = '2' if ver == '2.0' else ver
            msg = (
                f'Req {self._request_count:,} {request.method} {request.url.path} '
                f'HTTP/{ver} {response.status} {response.reason}'
            )
            self.logger.debug(msg)
            return

        duration = timedelta(seconds=stopped - started)
        self.logger.debug(f'Req {self._request_count:,} status={response.status} dur={duration}')
        self.logger.debug(f'{request.method} {request.url}')
        for key, val in request.headers.items():
            if key == 'Authorization':
                if val.startswith('Bearer ') and (tmp := val[len('Bearer '):]):
                    tmp = '*****' if len(tmp) <= 5 else f'{tmp[0]}***{tmp[-2:]}'
                    val = f'Bearer {tmp}'
            self.logger.debug(f'< {key}: {val}')
        self.logger.debug('')
        if request_payload:
            self.logger.debug(f'request={_masked_debug(request_payload)}')
            self.logger.debug('')

        self.logger.debug(f'HTTP {response.status} {response.reason} {response.version}')
        for key, val in response.headers.items():
            self.logger.debug(f'> {key}: {val}')
        self.logger.debug('')
        if response_payload:
            self.logger.debug(f'response={_masked_debug(response_payload)}')
            self.logger.debug('')

    async def request(self, method, path, data=None, attempts: int = 3) -> dict:

        if not isinstance(attempts, int) or attempts < 1:
            raise ValueError(f'attempts must be a positive integer.  not {attempts!r}')
        attempts = min(attempts, 20)  # default func signature, no more than 20

        if method not in ('GET', 'POST'):
            raise ValueError(f'"{method}" is not a supported method.  Only "GET" and "POST" are supported.')

        if method == 'POST' and data is None:
            data = {}

        url = f'{OWNER_BASE_URL}{path}'
        error = None

        # Sometimes we get routine upstream errors from the mothership.  As a convenience, the
        # `attempts` param can be increased when HTTP status code >= 500 or 408 timeout is
        # encountered.
        for attempt in range(1, attempts + 1):
            status, reason, payload = await self._request(method, url, data)
            if status == 401 and payload.get('error', '') == 'invalid bearer token':
                await self._credential.do_refresh_token()
                self.access_token = self._credential.access_token
                status, reason, payload = await self._request(method, url, data)
                status = 401 if status != 200 else status

            jdata = {
                'carsonRequest': {'url': url, 'method': method},
                'carsonTimestamp': datetime.now(tz=timezone.utc).isoformat(),

                'status': status,
                # The HTTP status code returned by `requests` package

                'response': payload.get('response', None) or {},
                # This is populated by Tesla unless there is an error

                'error': payload.get('error', reason if status != 200 else None),
                # Non network/protocol errors reported by Tesla.
                # Example: "https://mothership.prd.sjc.vnet:5678/vehicles/0123456789 => operation_timedout with 10s timeout for txid `99xxxxxxxxxxxxxxxxxxxxxxxxxxxx47`",
            }

            # If 408 Request Timeout or anything >= 500, retry
            if status != REQUEST_TIMEOUT or status < 500:
                if status >= 400:
                    raise TeslaSessionError(jdata)
                return jdata

            if attempt < attempts:
                sleep = 1.00784 * 3.141592653589793 * (attempt + 1)
                # Hydrogen x PI.  See the movie Contact

                self.logger.warning(
                    'Received HTTP=%d on attempt %d of %d.  Waiting %s before trying again.',
                    status,
                    attempt,
                    attempts,
                    timedelta(seconds=sleep).total_seconds()
                )
                await asyncio.sleep(sleep)

        raise TeslaSessionError(status=status, error=error)

    async def get(self, path, data=None):
        return await self.request('GET', path, data=data)

    async def post(self, path, data={}):
        return await self.request('POST', path, data=data)

    async def _request(self, method, url, data):
        started = self.timer()
        self._request_count += 1
        async with self._session.request(method, url, json=data) as response:
            payload = (
                # Some responses are not json (e.g. 503 Service Unavailable).  The
                # easiest thing to do would simply coerce everything to json.
                await response.json()
                if 'json' in response.content_type
                else await response.text()
            )
            ended = self.timer()
            if isinstance(payload, str):
                payload = {'text': payload}
            assert isinstance(payload, dict), f'({type(payload)}) payload={payload!r}'

            self._request_debug(response, payload, data, started, ended)

            status = response.status
            if status == 401 and 'WWW-Authenticate' in response.headers:
                payload['error'] = response.headers['WWW-Authenticate']

            return status, response.reason, payload


class NestedData:
    """
    Allows for dotted attribute notation on nested levels of JSON data.
    """
    def __init__(self, name, details):
        self.__name = name
        self.__details = details

    def __str__(self):
        return f'{self.__name}({self.__details})'

    def __getattribute__(self, attr):
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            pass

        if attr not in self.__details:
            attrs = ', '.join(repr(key) for key in self.__details)
            raise AttributeError(f'Could not find attribute {attr!r} in {self.__name!r}. Attrs={attrs}')

        val = self.__details.get(attr)
        if isinstance(val, dict):
            return NestedData(name=f'{self.__name}.{attr}', details=val)

        return val


class VehicleStateError(Exception):
    """
    A class to represent a sleeping car should not be disturbed.  Or offline,
    or... whatever.
    """
    def __init__(self, *args, **kwargs):
        self.msg = args[0] if len(args) and isinstance(args[0], str) else 'Car not in expected state'
        self.state = kwargs.pop('state', 'unknown')
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f'VehicleStateError({self.msg!r} state={self.state!r})'


class Vehicle:
    """
    Represents an individual Tesla vehicle.
    """

    def __init__(self, session, details=None):
        """
        Initializes an instance of a Tesla vehicle.

        Params:
          session: an instance of Session
          details: If not None, a `dict` parsed from JSON with contents
          resembling something like the following:
          {
            'backseat_token_updated_at': None,
            'backseat_token': None,
            'calendar_enabled': True,
            'color': None,
            'display_name': 'Red Pill',
            'id_s': '462..........773',
            'id': 462..........773,
            'in_service': False,
            'option_codes': 'AD15,MDL3,PBS...',
            'state': 'online',
            'tokens': ['87c..........6bf', '0f7..........172'],
            'vehicle_id': 0123456789,
            'vin': '5YJ...8',
          }
        """
        self._session = session
        self._override = {}
        self.display_name = 'Tesla'
        self.state = 'unknown'
        self.tokens = []

        if details is not None:
            self._init_from(details)

    def __getattribute__(self, attr):

        attr = 'display_name' if attr == 'name' else attr
        # The `name`` attribute is an implicit alias for `display_name`.`

        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            pass

        if attr in self._override:
            val = self._override.get(attr)
            if isinstance(val, dict):
                return NestedData(name=f'Vehicle.{attr}', details=val)
            return val

        endpoint = endpoints.MAP_ATTR_TO_ENDPOINT.get(attr.upper(), None)
        if not endpoint:
            raise AttributeError(f'Attribute {attr!r} not found.')

        method = endpoint['TYPE']
        uri = endpoint['URI'].replace('{vehicle_id}', '{id}')
        uri = '/{}'.format(uri.format(**self.__dict__))
        car = self

        async def func():
            return await car._session.request(method, uri)
        return func

    def _init_from(self, obj):
        assert isinstance(obj, dict), f'obj=({obj.__class__.__name__}) {obj!r}'
        for key, val in obj.items():
            if key in LEGACY_ATTRIBUTES:
                continue

            # If what we are setting is already defined as a property, store it
            # in the _override dict instead.
            if hasattr(Vehicle, key):
                assert isinstance(val, dict)
                self._override[key] = val
            elif isinstance(val, dict):
                self._override[key] = val
            else:
                setattr(self, key, val)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        # Spits out something like Vehicle(name state='online' ... speed=12).
        # The `attrs` are the values to include, if the object has them, and
        # optionally if the value does not evaluate to be something specific.
        # And, again optionally, a formatter function.

        buf = []

        attrs = tuple("""
            display_name
            state
            in_service
            id
            vehicle_state.is_user_present
            vehicle_state.sentry_mode
            vehicle_state.odometer
            vehicle_state.car_version
            charge_state.battery_level
            charge_state.charging_state
            charge_state.time_to_full_charge
            drive_state.shift_state
            drive_state.speed
        """.split())

        unless_eqs = {
            'in_service': False,
            'vehicle_state.is_user_present': False,
            'vehicle_state.sentry_mode': False,
            'charge_state.time_to_full_charge': 0
        }

        formatters = {
            'display_name': lambda val: repr(val),
            'in_service': lambda val: '(In Service)',
            'vehicle_state.odometer': lambda val: f'miles={int(val):,}',
            'vehicle_state.car_version': lambda val: 'software={}'.format(repr(val.split(' ')[0])),
            'charge_state.time_to_full_charge': lambda val: str(timedelta(seconds=float(val) * 60 * 60)) + ' remaining'
        }

        for attr in attrs:
            unless_eq = unless_eqs.get(attr, None)
            fmt = formatters.get(attr, None)

            try:
                # The value can be part of ourself (e.g. in self.__dict__) which
                # we will check first.
                if attr in self.__dict__:
                    val = self.__dict__[attr]
                else:
                    # If not, assume the attr is a path into sub objects which
                    # each level denoted by `.`.
                    obj = self
                    while attr.count('.'):
                        prop, attr = attr.split('.', 1)
                        obj = getattr(obj, prop)
                    val = getattr(obj, attr)

                # If it's a default value we don't want to display in the repr
                # value, just skip it.  This could be either an exact match `val == unless_eq` or
                # if `unless_eq` is a tuple and `val in unless_eq`
                if val == unless_eq or isinstance(unless_eq, (list, tuple)) and val in unless_eq:
                    continue

                # If it's a default value

                # Otherwise repr the pair or use formatter (if given).
                val = fmt(val) if fmt else f'{attr}={val!r}'
                if val:
                    buf.append(val)

            except AttributeError:
                # If a car is offline and we don't have the data, we won't have
                # the attribute.  Online cars may also not have the attribute if
                # a call has not yet been made to:
                #   `api/1/vehicles/{vehicle_id}/vehicle_data`
                pass

            except Exception as err:
                # Something else is wrong.
                buf.append(f'{attr}={err}')

        return 'Vehicle({})'.format(' '.join(buf))

    async def close(self):
        return await self._session.close()

    @property
    def logger(self):
        if self._session:
            return self._session.logger
        from .logging import logger
        return logger

    @property
    def token(self):
        """
        Careful!  A `token` is not the same thing as an access token.

        Usually `self.tokens` is a list of two tokens.  Either of them will do (I think).  But
        instead of checking their existance and then picking the first one every time we need
        one in various places in the code, let a property do the dirty work for you.
        """
        return self.tokens[0] if self.tokens else 'none'

    @property
    def access_token(self):
        """
        Not to be confused with self.token
        """
        return self._session.access_token if self._session else None

    @property
    def email(self):
        return self._session.email if self._session else None

    @property
    def is_charging(self):
        cstate = 'Unknown'
        try:
            cstate = self.charge_state.charging_state
        except AttributeError:
            pass
        return cstate == 'Charging'

    async def actuate_trunk(self, which):
        args = ('POST', f'/api/1/vehicles/{self.id}/command/actuate_trunk')
        kwargs = {'data': {'which_trunk': which}}
        return await self._session.request(*args, **kwargs)

    async def open_trunk(self):
        return await self.actuate_trunk('rear')

    async def open_frunk(self):
        return await self.actuate_trunk('front')

    async def wake_up(self):
        if self.in_service:
            raise VehicleStateError('Vehicle is in service.', state=self.state)

        # curl -i --oauth2-bearer 99***7c --data "" https://owner-api.teslamotors.com/api/1/vehicles/12345678901234567/wake_up
        previous_state = self.state
        attempts = 20
        self.state = 'wakeup'
        await self._session.post(f'/api/1/vehicles/{self.id}/wake_up')
        self.logger.debug('Waiting for car to wake up. attempts=%d', attempts)
        try:
            path = f'/api/1/vehicles/{self.id}/vehicle_data'
            jdata = await self._session.request('GET', path, attempts=attempts)
        except TeslaSessionError:
            self.state = previous_state
            raise

        self._init_from(jdata.get('response'))
        return self.dump()

    async def data(self):
        """
        Makes call to Tesla to get current information about the vehicle.  But
        the car must be online.  Otherwise a VehicleStateError is raised.
        """
        # curl -i --oauth2-bearer 99***7c  https://owner-api.teslamotors.com/api/1/vehicles/12345678901234567/vehicle_data

        if self.state not in ('online', 'wakeup'):
            raise VehicleStateError('Car is not online.', state=self.state)

        attempts = 20 if self.state == 'wakeup' else 3
        # If we are waking up, try more than if we are just 'online' because we
        # could have gone back to sleep.

        jdata = await self._session.request('GET', f'/api/1/vehicles/{self.id}/vehicle_data', attempts=attempts)
        status = jdata.get('status')
        if status == 200:
            self._init_from(jdata.get('response'))
            return self.dump()

        if status == REQUEST_TIMEOUT:
            msg = 'Car is no longer online.'
            old_state = self.state
            if old_state == 'wakeup':
                msg = 'Could not wake up car.'
            self.state = 'unknown'
            raise VehicleStateError(msg, state=old_state)

        self.logger.error('Could not get a good response for data.  resp=%r', jdata)
        raise TeslaSessionError('Could not get a good response.', response=jdata)

    def clear(self):
        self._override.clear()
        self.tokens.clear()
        self.state = 'unknown'
        keys = set(k for k in self.__dict__ if not k.startswith('_'))
        keys.difference_update([
            'display_name', 'state', 'tokens',
            'id', 'id_s', 'vehicle_id', 'vin'
        ])
        for attr in keys:
            delattr(self, attr)

    async def refresh(self):
        """
        Performs a 'soft' refreshing of the current state and vehicle tokens.  Designed to not wake
        up the car, if we can help it.  Essentially we just do a vehicle list with the base session
        which includes a current status of the car.
        """
        self.clear()

        jdata = await self._session.get('/api/1/vehicles')
        vehicles = jdata.get('response', None) or []
        for vehicle in vehicles:
            if vehicle.get('vehicle_id') == self.vehicle_id:
                self._init_from(vehicle)
                return
        raise TeslaSessionError('Could not refresh self!  Car not found!', response=jdata)

    def dump(self):
        dumpable = {attr: val for attr, val in self.__dict__.items() if not attr.startswith('_')}
        dumpable.update({key: val for key, val in self._override.items()})
        return dumpable

    def pformat(self):
        return pformat(self.dump(), width=100)

    async def start_charge(self):
        """
        Will attempt to start charging the car.  Requires the car to not be
        asleep.  Otherwise a 408 will be returned.
        """
        return await self._session.post(f'/api/1/vehicles/{self.id}/command/charge_start')

    async def stream(self, *, callback=None):
        if self.state != 'online':
            raise VehicleStateError('Car must be online to stream.', state=self.state)

        from .stream import stream as _stream
        return await _stream(self, callback=callback)

    async def ws_connect(self, *args, **kwargs):
        if not self._session:
            raise TeslaSessionError('Not connected.')
        return await self._session.ws_connect(*args, **kwargs)


def _masked_debug(d):
    if d is None:
        return None

    assert isinstance(d, (str, dict)), type(d)

    if isinstance(d, str):
        if len(d) < 5:
            return '***'
        return f'{d[:3]}***{d[-3:]}'

    buf = []
    for key in sorted(d):
        assert isinstance(key, str)
        val = '***' if key.lower() == 'password' else d.get(key)
        if val and key.lower() in ('authorization', 'access_token'):
            val = '***' if len(val) < 5 else f'{val[:3]}***{val[-3:]}'
        buf.append(f'{key!r}: {val!r}')
    return f'{{{", ".join(buf)}}}'
