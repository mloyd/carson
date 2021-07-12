"""
The basic classes representing a connection with the Tesla web service and the
cars on your account.
"""

import asyncio
import configparser
import json
import time
from datetime import datetime, timedelta
from pprint import pformat

import aiohttp

from . import config, logging, auth, utils, endpoints, get_version


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

BASEURL = 'https://owner-api.teslamotors.com'


class TeslaSessionError(Exception):
    """
    Represents a generic exception raised when the expected response from the Tesla web service
    request is not as expected.
    """
    def __init__(self, *args, **kwargs):

        self.response = kwargs.pop('response', None)
        # The JSON response returned from the Tesla endpoint.

        self.status = self.response.get('status') if self.response else None
        # The HTTP response status code

        super().__init__(*args, **kwargs)


class TeslaCredentialError(TeslaSessionError):
    """
    Raised when anything other than status 200 is returned from a login attempt
    """
    pass


class Session:
    """
    Creates a session context to Tesla given the provided credentials or
    inferring from config.

    email:
      The email/user associated with the tesla.com account.

    password:
      The password associated with the email/user account.

    access_token:
      Can be used in lieu of email/password if already generated.

    If `password` is given, access_token is ignored.  Likewise, if `password` is
    given, any token stored in config will be ignored.
    """

    def __init__(self, email=None, password=None, access_token=None, verbose=0):
        self.email = email or config.get('email')
        self.password = password
        self.verbose = 1 if verbose is True else verbose

        self.logger = logging
        # If you want to set your own logger

        self.auth = {
            'access_token': access_token or config.get('access_token'),
            # Authorization token used to make requests.  Translates to HTTP
            # header value in the form:
            #     Authorization: Bearer <token>

            'created_at': config.getint('created_at', 0),
            # The Unix timestamp value (UTC) returned when generating an auth
            # token.  Number of seconds since 1970.

            'expires_in': config.getint('expires_in', 0),
            # The number of seconds returned from auth_timestamp the token will
            # expire.  Sometimes it's big like 45 days.

            'refresh_token': config.get('refresh_token'),
        }

        if password:
            self.auth['access_token'] = None
            self.auth['created_at'] = 0
            self.auth['expires_in'] = 0
        elif not self.auth['access_token']:
            self.password = config.get('password')

        self._vehicles = {}
        # Our cached vehicles which maps name to instance of vehicle.

        self._request_count = 0
        # How many outbound reqeusts have been made.

        self._session = None
        # Will not create an aoihttp session until the first request.

        self.timer = time.monotonic

    @property
    def expires(self):
        dt = datetime(1970, 1, 1)
        created_at = self.auth.get('created_at', 0)
        expires_in = self.auth.get('expires_in', 0)
        if not created_at or not expires_in:
            return None
        return dt + timedelta(seconds=created_at + expires_in)

    @property
    def expired(self):
        # Careful, this is not a truthy. Can return None if unknown.
        exp = self.expires
        if exp is None:
            return None
        return self.expires < datetime.utcnow()

    @property
    def access_token(self):
        return self.auth.get('access_token', None)

    def __str__(self):
        buf = f'<Session email={self.email!r}'

        # If `self._vehicles` is empty, it doesn't mean we don't have any.  So
        # don't report zero.  But we shouldn't make a request simply to get the
        # number of vehichles either.  Unless this would not be the first
        # request.
        if self._vehicles or self._request_count:
            buf += f' vehicles={len(self.vehicles):,}'

        if self.auth.get('access_token', None):
            # If we have an auth token, show that it is expired or when it will
            # expire.
            exp = self.expired
            if exp:
                buf += ' expired'
            else:
                exps = 'Unknown' if exp is None else str(self.expires - datetime.utcnow())
                buf += f' expires={exps}'

        return buf + '>'

    def _create_session(self, access_token=None):
        default_headers = {'User-Agent': f'carson/{get_version()}'}
        if access_token:
            default_headers['Authorization'] = f'Bearer {access_token}'
            if self.verbose > 2:
                self.logger.debug('Creating client session with access token')
        elif self.verbose > 2:
            self.logger.debug('Creating client session WITHOUT access token')
        return aiohttp.ClientSession(headers=default_headers)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.verbose > 2:
            self.logger.debug('Session.__exit__(exc_type=%r  exc_value=%r  traceback=%r', exc_type, exc_value, traceback)
        assert not self._session or self._session.closed

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.logger.debug('Session.__aexit__(exc_type=%r  exc_value=%r  traceback=%r', exc_type, exc_value, traceback)
        await self.close()

    async def close(self):
        if self._session:
            if not self._session.closed:
                await self._session.close()
            self._session = None

    async def login(self):

        self.auth = {'access_token': None, 'refresh_token': None, 'created_at': 0, 'expires_in': 0}
        config.setitems(self.auth)

        # We want to explicitly close any current session to make sure we
        # expunge the bearer token.  This makes sure it matches what we just
        # wrote to config which is access_token=None.
        await self.close()

        missing = [attr for attr in ('email', 'password') if not getattr(self, attr)]
        if missing:
            missing = ', '.join(missing)
            raise TeslaCredentialError(f'Cannot login.  Missing attributes: {missing}.')

        try:
            new_auth = await auth.get_auth_data(self.email, self.password)
        except Exception:
            self.logger.error('Could not authenticate.', exc_info=True)
            raise TeslaCredentialError()

        newdata = {k: new_auth.get(k) for k in self.auth if k in new_auth}
        self.auth.update(newdata)
        config.set('email', self.email)
        config.setitems(self.auth)
        config.save()
        self._session = self._create_session(access_token=self.auth.get('access_token'))

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
        if not self._session or self._session.closed:
            # If we don't have a session, create an instance using an access
            # token if we have one.
            self._session = self._create_session(access_token=self.auth.get('access_token'))

        if 'Authorization' not in self._session._default_headers:
            # If creating a session using an access token did not result in us
            # having an auth header, try to login.  Will raise
            # TeslaCredentialError if it fails.
            await self.login()

        return await self._session.ws_connect(*args, **kwargs)

    async def request(self, method, path, data=None, attempts=1):

        if not self._session or self._session.closed:
            # If we don't have a session, create an instance using an access
            # token if we have one.
            self._session = self._create_session(access_token=self.auth.get('access_token'))

        if 'Authorization' not in self._session._default_headers:
            # If creating a session using an access token did not result in us
            # having an auth header, try to login.  Will raise
            # TeslaCredentialError if it fails.
            await self.login()

        if method not in ('GET', 'POST'):
            raise ValueError(f'"{method}" is not a supported method.  Only "GET" and "POST" are supported.')

        url = f'{BASEURL}{path}'

        jdata = {
            'carsonRequest': {'url': url, 'method': method},
            'carsonTimestamp': datetime.utcnow().isoformat(),

            'status': 0,
            # The HTTP status code returned by `requests` package

            'response': {},
            # This is populated by Tesla unless there is an error

            'error': None,
            # Non network/protocol errors reported by Tesla.
            # Example: "https://mothership.prd.sjc.vnet:5678/vehicles/0123456789 => operation_timedout with 10s timeout for txid `99xxxxxxxxxxxxxxxxxxxxxxxxxxxx47`",

            "error_description": '',
            # Provided by Tesla when 'error' is present.  But I have never seen
            # anything other than an empty string.
        }

        # Sometimes we get routine upstream errors from the mothership.  As a convenience, the
        # `attempts` param can be increased when HTTP status code >= 500 or 408 timeout is
        # encountered.
        # TODO: Make configurable by HTTP status code?
        if not isinstance(attempts, int) or attempts < 1:
            attempts = 1
        attempts = min(attempts, 20)
        logmsg = ''
        for attempt in range(1, attempts + 1):
            self._request_count += 1

            rstart = 0
            rstop = 0
            if self.verbose:
                rstart = self.timer()
                rstop = rstart
                logmsg = f'Req# {self._request_count:,}'
                if attempt > 1:
                    logmsg += f' (attempt #{attempt:,} of {attempts:,})'
                logmsg += f':  Method={method} url={url!r}'
                if data:
                    logmsg += f' data={_masked_debug(data)!r}'
                if self.verbose > 2:
                    self.logger.debug('=' * 110)
                if self.verbose >= 2:
                    self.logger.debug(logmsg)

            resp = await self._session.request(method, url, data=data)
            jdata['status'] = resp.status

            real_url = str(resp.real_url)
            if real_url != url:
                # e.g. redirect
                jdata['carsonRequest'] = {
                    'endpoint': url,
                    'method': method,
                    'url': real_url
                }

            if self.verbose:
                rstop = self.timer()
                if self.verbose == 1:
                    logmsg += f' status={resp.status!r} duration={timedelta(seconds=rstop - rstart)}'
                    self.logger.debug(logmsg)
                else:
                    self.logger.debug(f'Req# {self._request_count}:  Response received. status={resp.status!r} duration={timedelta(seconds=rstop - rstart)}')
                if self.verbose > 2:
                    for i, (key, val) in enumerate(resp.headers.items()):
                        self.logger.debug(f'Header {i:,}: {key: <30}  {val}')
                    self.logger.debug('=' * 110)

            txt = await resp.text()
            content_type = resp.headers.get('Content-Type', 'unknown')
            if self.verbose > 1:
                self.logger.debug(f'content_type={content_type!r} txt={txt!r}')

            if txt and 'json' in content_type.lower():
                try:
                    jdata.update(utils.json_loads(txt))
                except json.decoder.JSONDecodeError:
                    jdata['error'] = 'json.decoder.JSONDecodeError'
                    jdata['error_description'] = f'resp.text={resp.text!r}'
                    self.logger.error('Response indicated a JSON response.  But parsing produced an error.')
                    self.logger.error('resp.text=%r\ndata=%r', resp.text, jdata, exc_info=True)
            else:
                # Then we have no idea what's going on.
                jdata['error'] = txt

            # We will re-try a 408 and anything in the 500s.
            if resp.status == 408 or resp.status >= 500:
                if attempts > 1:
                    logmsg = 'Received status code {} on attempt {:,} of {:,}.'
                    logargs = [resp.status, attempt, attempts]
                else:
                    logmsg = 'Received status code {}.'
                    logargs = [resp.status]

                if attempt < attempts:
                    logmsg += ' Sleeping {:.2f} before retry.  Content-Type={!r} txt={!r}'

                    sleep = 1.00784 * 3.141592653589793 * (attempt + 1)
                    # Hydrogen x PI.  See the movie Contact

                    logargs.extend([sleep, content_type, txt])
                    self.logger.warning(logmsg.format(*logargs))
                    await asyncio.sleep(sleep)
                else:
                    raise TeslaSessionError(logmsg.format(*logargs), response=jdata)

            else:
                break

        return jdata

    async def get(self, path, data=None):
        return await self.request('GET', path, data=data)

    async def post(self, path, data={}):
        return await self.request('POST', path, data=data)


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
        return self._session and self._session.logger or logging.logger

    @property
    def token(self):
        """
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
        return self._session.auth.get('access_token') if self._session else None

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
        await self._session.request('POST', f'/api/1/vehicles/{self.id}/wake_up')

        self.state = 'wakeup'

        attempts = 20
        for attempt in range(1, attempts + 1):
            self.logger.debug('Waiting for car to wake up. #%d of %d', attempt, attempts)
            try:
                jdata = await self._session.request('GET', f'/api/1/vehicles/{self.id}/vehicle_data')
                self._init_from(jdata.get('response'))
                return self.dump()
            except TeslaSessionError as err:
                if err.status != 408 or attempt == attempts:
                    self.state = previous_state
                    raise
                await asyncio.sleep(1)

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

        if status == 408:
            msg = 'Car is no longer online.'
            if self.state == 'wakeup':
                msg = 'Could not wake up car.'
            self.state = 'unknown'
            raise VehicleStateError(msg)

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

    assert isinstance(d, str) or isinstance(d, dict), type(d)

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
