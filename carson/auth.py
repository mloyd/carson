"""
This whole module and approach is a hack.  It's not well documented because it's not official.  But
the horse is out of the barn on this stuff and we have to do something.
"""

import base64, hashlib, random, re, string, ssl
from urllib.parse import urlencode, urlparse, parse_qs

import aiohttp
from . import logging as logger
from ._version import get_version


CHARS = f'{string.digits}{string.ascii_letters}'

# When parsing the HTML output of the login page
RE_INPUT = re.compile(r'<\s*input\s+[^>]*>', re.IGNORECASE)
RE_NAME = re.compile(r'name\s*=\s*"?(?P<name>[^ "]+)?', re.IGNORECASE)
RE_VALUE = re.compile(r'value\s*=\s*"?(?P<value>[^ "]+)?', re.IGNORECASE)
MAX_FIELDS = 50


async def get_auth_data(identity, credential):
    """
    Accepts identity (a.k.a email) and credential (a.k.a password) and returns your tokens.  This
    currently does not support mfa.

    Returns:
        dict {
            "access_token": "<access_token>",
            "token_type": "bearer",
            "expires_in": <seconds>,  # Have only seen 45 days
            "refresh_token": "<refresh_token>",
            "created_at": <epoch>
        }
    """
    our_code, challenge1, challenge2 = _get_challengers()

    v = f'carson/{get_version().version}'
    async with aiohttp.ClientSession(headers={'User-Agent': v}) as session:
        issuer, their_code, redirect_uri = await get_and_post_login_page(session, identity, credential, challenge1, challenge2)
        tokens = await post_grant_authorization_code(session, issuer, our_code, their_code, redirect_uri, challenge2)
        return tokens


async def get_and_post_login_page(session, identity, credential, challenge1, challenge2):

    # TODO: At one time, capping TLS to 1.2 was required but this is probably not needed anymore.
    ssl_context = ssl.create_default_context()
    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2

    query = {
        'client_id':             'ownerapi',
        'code_challenge':        challenge1,
        'code_challenge_method': 'S256',
        'locale':                'en',
        'prompt':                'login',
        'redirect_uri':          'https://auth.tesla.com/void/callback',
        'response_type':         'code',
        'scope':                 'openid email offline_access',
        'state':                 challenge2
    }

    auth_url = 'https://auth-global.tesla.com/oauth2/v3/authorize'
    request_url = f'{auth_url}?{urlencode(query)}'
    response_url = None
    login_form = {}
    async with session.get(request_url, ssl=ssl_context) as response:
        # _debug_response(response)
        response_url = f'{response.request_info.url}'
        login_form = parse_html(await response.text())

    login_form.update({'identity': identity, 'credential': credential})
    async with session.post(response_url, data=login_form, ssl=ssl_context, allow_redirects=False) as response:
        # _debug_response(response)
        _loc = response.headers.get('location')
        txt = await response.text()

    if not _loc:
        if 'captcha' in txt:
            raise Exception('Looks like captcha is required.')
        raise Exception('Did not get a redirect from posting credentials')

    location = urlparse(_loc)

    mfa = '/oauth2/v3/authorize/mfa/verify' in txt
    assert not mfa, 'Not supporting MFA at this time.'

    query = parse_qs(location.query)
    their_code = query.get('code', [None])[0]
    issuer = query.get('issuer', [None])[0]
    if not their_code:
        raise Exception('Did not get a code back from posting credentials.')

    redirect_uri = f'{location.scheme}://{location.netloc}{location.path}'
    return issuer, their_code, redirect_uri


async def post_grant_authorization_code(session, issuer, our_code, their_code, redirect_uri, challenge2):
    form = {
        'grant_type': 'authorization_code',
        'client_id': 'ownerapi',
        'code_verifier': our_code,
        'code': their_code,
        'redirect_uri': redirect_uri
    }
    issuer = issuer or 'https://auth.tesla.com/oauth2/v3'
    issuer_url = f'{issuer}/token'

    async with session.post(issuer_url, json=form) as response:
        tokens = await response.json()

    if 'state' not in tokens or str(tokens['state']) != challenge2:
        logger.error(f'Returned state ({tokens.get("state", None)!r}) did not match expected value ({challenge2!r})')
        raise Exception('Returned authorization_code state did not match expected value')

    # post_grant_jwt
    url = 'https://owner-api.teslamotors.com/oauth/token'
    headers = {'Authorization': f'Bearer {tokens.get("access_token")}'}
    form = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'client_id': _DISCOVERED_VAL,
    }
    async with session.post(url, headers=headers, json=form) as response:
        # _debug_response(response)
        return await response.json()


def parse_html(body_src):
    form = {}
    field_nbr = 0

    input_match = RE_INPUT.search(body_src)
    while input_match:
        field_nbr += 1
        if field_nbr > MAX_FIELDS:
            raise ValueError(f'Too many input fields found. max={MAX_FIELDS:,}')

        b, e = input_match.span()
        input_src, body_src = body_src[b:e], body_src[e:]
        input_match = RE_INPUT.search(body_src)

        name_match = RE_NAME.search(input_src)
        if not name_match or not name_match.group('name'):
            continue

        value_match = RE_VALUE.search(input_src)
        form[name_match.group('name')] = value_match and value_match.group('value') or ''

    return form


def _get_challengers():
    code = ''.join(random.choices(CHARS, k=112))
    sha = hashlib.sha256()
    sha.update(code.encode())
    challenge1 = base64.b64encode(sha.digest(), altchars=b'-_').decode().replace('=', '')
    sha.update(''.join(random.choices(CHARS, k=112)).encode())
    challenge2 = base64.b64encode(sha.digest(), altchars=b'-_').decode().replace('=', '')
    return code, challenge1, challenge2


_DISCOVERED_VAL = ''.join(hex(int(val))[2:] for val in """
    08  01  05  02  07  12  15  15
    00  06  08  04  03  12  08  06
    03  04  15  13  12  00  09  14
    08  10  12  00  10  11  14  15
    11  04  06  10  12  08  04  09
    15  03  08  15  14  01  14  04
    03  01  12  02  14  15  02  01
    00  06  07  09  06  03  08  04
""".split())


def _debug_response(response):
    req = response.request_info
    logger.debug('Request')
    logger.debug(f'{req.method} {req.url}')
    for key, val in req.headers.items():
        logger.debug(f'{key}: {val}')
    logger.debug('')
    logger.debug('Response')
    logger.debug(f'HTTP {response.status} {response.reason}')
    for key, val in response.raw_headers:
        logger.debug(f'{key.decode()}: {val.decode()}')
    logger.debug('')
