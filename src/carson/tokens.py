import asyncio, logging, inspect
from datetime import datetime, timezone
from aiohttp import ClientSession

from . import OWNER_BASE_URL

AUTH_BASE_URL = 'https://auth.tesla.com/oauth2/v3'

jwt = None
try:
    import jwt

    # We try to import cryptography too because it's optional for jwt, however, required for what
    # we are doing.  If it raises a ModuleNotFoundError it's effectively the same as jwt not being
    # installed.
    import cryptography  # noqa: F401
except ModuleNotFoundError:
    jwt = None

WELL_KNOWN = f'{AUTH_BASE_URL}/.well-known/openid-configuration'
JWKS_URI = f'{AUTH_BASE_URL}/discovery/keys'
TOKEN_URI = f'{AUTH_BASE_URL}/token'
AUDIENCES = {
    'id_token': 'ownerapi',
    'refresh_token': TOKEN_URI,
    'access_token': [OWNER_BASE_URL, f'{AUTH_BASE_URL}/userinfo'],
}

logger = logging.getLogger(__name__)


class Credential:
    access_token: str
    refresh_token: str
    id_token: str
    expires_in: int
    created_at: int
    token_type: str

    def __init__(self, credential):
        self._credential = credential
        self._refresh_callbacks = []

        # Test the credential object to ensure it meets the expected read mechanism.
        if not isinstance(self._credential, dict):
            errors = []
            for attr in TOKEN_ATTRS:
                try:
                    self._credential[attr]
                except (TypeError, AttributeError, KeyError) as exc:
                    # TypeError      raised on objects not supporting __getattribute__ (a.k.a. primitives, custom)
                    # AttributeError raised on objects that support __getattribute__ but don't have it.
                    # KeyError       raised on a dict if it doesn't have it.
                    errors.append(f'{type(exc).__name__} when trying to get {attr!r}  {exc}')
            if errors:
                msg = '\n'.join(f' - {err}' for err in errors)
                raise TypeError(f'Token attribute error(s) on credential.\n{msg}')

    def __getattribute__(self, name: str):
        if name in TOKEN_ATTRS:
            _cred = super().__getattribute__('_credential')
            if isinstance(_cred, dict) and name not in _cred:
                return None
            return _cred[name]
        return super().__getattribute__(name)

    def __setattr__(self, name: str, val):
        if name in TOKEN_ATTRS:
            vtype = TOKEN_ATTRS[name]
            if val is None:
                val = {int: 0, str: ''}.get(vtype, val)
            if vtype == int and isinstance(val, str) and val.isnumeric():
                val = int(val)
            if type(val) != vtype:
                raise ValueError(f'Expected {vtype} for {name!r}.  Not {type(val)}')
            _cred = super().__getattribute__('_credential')
            _cred[name] = val
        else:
            super().__setattr__(name, val)

    def add_refresh_callback(self, item: callable):
        if item in self._refresh_callbacks:
            self._refresh_callbacks.remove(item)
        self._refresh_callbacks.append(item)

    async def do_refresh_token(self) -> dict:
        if not self.access_token or not self.refresh_token:
            raise Exception('Must have both access/refresh tokens or refresh.')

        payload = {
            'grant_type': 'refresh_token',
            'client_id': 'ownerapi',
            'refresh_token': self.refresh_token,
            'scope': 'openid email offline_access'
        }
        headers = {'Authorization': f'Bearer {self.access_token}'}
        async with ClientSession(headers=headers) as client:
            async with client.post(TOKEN_URI, json=payload) as response:
                new_tokens = (
                    await response.json()
                    if 'json' in response.content_type
                    else await response.text()
                )
                status = response.status
                if status != 200 or not isinstance(new_tokens, dict):
                    error = (
                        f'Unexpected response from token refresh. Code={status}\n'
                        f'Content-Type={response.content_type!r}\n'
                        f'Response: {new_tokens}'
                    )
                    raise Exception(error)

        current = {
            key: str(getattr(self, key, None) or '')
            for key in TOKEN_ATTRS
            if key != 'created_at'
        }
        updates = {
            key: val
            for key, val in new_tokens.items()
            if key in TOKEN_ATTRS
            and str(val) != current[key]
        }

        if not updates:
            logger.debug('Nothing updated after attempting token refresh.')
        else:
            await _verify_jwt(updates)
            for key, val in updates.items():
                setattr(self, key, val)
            created_at = int(datetime.now(tz=timezone.utc).timestamp())
            self.created_at = created_at
            updates['created_at'] = created_at

            uncallables = [func for func in self._refresh_callbacks if not callable(func)]
            if uncallables:
                logger.error('Cannot invoke callbacks. %s', ', '.join(str(func) for func in uncallables))

            _called = False
            for callback in [func for func in self._refresh_callbacks if callable(func)]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(updates)
                else:
                    callback(updates)
                _called = True

            if not _called:
                logger.warning('Token refreshed but no callbacks invoked!')

        return updates


async def _verify_jwt(tokens: dict):
    """
    If jwt is installed, verify signatures, audience, etc.  Expecting jwt library to raise relevant
    exceptions.  Default is to check expiration, audience,

    Ref: https://pyjwt.readthedocs.io/en/stable/usage.html
    """

    if jwt is None:
        logger.error('Cannot verify tokens.  PyJWT and cryptography both must be installed.')
        return

    async with ClientSession() as client:
        async with client.get(WELL_KNOWN) as response:
            data = await response.json()
    jwks_uri = data.get('jwks_uri', None) or JWKS_URI
    jwkc = jwt.PyJWKClient(jwks_uri)
    for name, token in tokens.items():
        if name not in AUDIENCES:
            continue
        signing_key = jwkc.get_signing_key_from_jwt(token)
        jwt.decode(
            token,
            signing_key.key,
            audience=AUDIENCES[name],
            algorithms=['RS256'],
        )


TOKEN_ATTRS = {
    key: val
    for key, val in inspect.get_annotations(Credential).items()
}
