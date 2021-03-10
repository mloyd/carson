"""
This whole module and approach is a hack.  It's not well documented because it's not official.  But
the horse is out of the barn on this stuff and we have to do something.
"""

import asyncio, base64, hashlib, random, re, string
from urllib.parse import urlencode, urlparse, parse_qs
from pprint import pformat

import aiohttp
from . import logging, __version__ as _version

CHARS = f'{string.digits}{string.ascii_letters}'
AUTH_URL = 'https://auth-global.tesla.com/oauth2/v3/authorize'

# When parsing the HTML output of the login page
RE_INPUT = re.compile(r'<\s*input\s+[^>]*>', re.IGNORECASE)
RE_NAME = re.compile(r'name\s*=\s*"?(?P<name>[^ "]+)?', re.IGNORECASE)
RE_VALUE = re.compile(r'value\s*=\s*"?(?P<value>[^ "]+)?', re.IGNORECASE)
MAX_FIELDS = 50


async def get_auth_data(identity, credential, logger=logging):
    our_code, challenge1 = _get_challenge_pair()
    _, challenge2 = _get_challenge_pair()
    logger.debug('our_code=%r  challenge1=%r  challenge2=%r', our_code, challenge1, challenge2)

    transaction_id = None  # Saved transaction ID to MFA

    async with aiohttp.ClientSession(headers={'User-Agent': f'carson/{_version}'}) as session:
        url, form = await get_login_page(session, challenge1, challenge2, logger)
        logger.debug('url: %s', url)
        logger.debug('form: %s', pformat(form))

        creds = {'identity': identity, 'credential': credential}
        issuer, their_code, redirect_uri = await post_credentials(session, url, form, creds, logger)
        logger.debug('issuer=%s  their_code=%s  redirect_uri=%s', issuer, their_code, redirect_uri)

        tokens = await post_grant_authorization_code(session, issuer, our_code, their_code, redirect_uri, logger)
        logger.debug('tokens=%s', pformat(tokens))
        state = tokens.get('state', None)
        if not state == challenge2:
            logger.error(f'Returned state ({state!r}) did not match expected value ({challenge2!r})')
            raise Exception(f'Returned authorization_code state did not match expected value')

        new_auth = await post_grant_jwt(session, tokens, logger)
        logger.debug('new_auth=%s', pformat(new_auth))
        return new_auth


async def get_login_page(session, challenge1, challenge2, logger):
    query = {
        'audience':              '',
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
    headers = {
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document'
    }

    request_url = f'{AUTH_URL}?{urlencode(query)}'
    async with session.get(request_url, headers=headers) as response:
        _debug_response(response, logger)
        response_url = f'{response.request_info.url}'
        return response_url, parse_html(await response.text(errors='replace'))


async def post_credentials(session, url, form, creds, logger):
    form.update(creds)
    url_parts = urlparse(url)
    headers = {
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': url,
        'origin': f'{url_parts.scheme}://{url_parts.netloc}',
    }
    async with session.post(url, headers=headers, data=form, allow_redirects=False) as response:
        _debug_response(response, logger)
        if 'location' not in response.headers:
            raise Exception('Did not get a redirect from posting credentials')
        if response.status not in (301, 302,):
            raise Exception('Did not get a HTTP 301/302 redirect from posting credentials')
        location = urlparse(response.headers['location'])

        txt = '' if not response.content_length else await response.text()
        logger.debug('txt=%r', txt)
        mfa = '/oauth2/v3/authorize/mfa/verify' in txt
        assert not mfa, 'Not supporting MFA at this time.'

        query = parse_qs(location.query)
        their_code = query.get('code', [None])[0]
        if not their_code:
            raise Exception(f'Did not get a code back from posting credentials.')
        issuer = query.get('issuer', ['https://auth.tesla.com/oauth2/v3'])[0]
        redirect_uri = f'{location.scheme}://{location.netloc}{location.path}'
        return issuer, their_code, redirect_uri


async def post_grant_authorization_code(session, issuer, our_code, their_code, redirect_uri, logger):
    form = {
        'grant_type': 'authorization_code',
        'client_id': 'ownerapi',
        'code_verifier': our_code,
        'code': their_code,
        'redirect_uri': redirect_uri
    }
    async with session.post(f'{issuer}/token', json=form) as response:
        _debug_response(response, logger)
        return await response.json()


async def post_grant_jwt(session, tokens, logger):
    url = 'https://owner-api.teslamotors.com/oauth/token'
    headers = {'Authorization': f'Bearer {tokens.get("access_token")}'}
    form = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'client_id': _DISCOVERED_VAL,
    }
    async with session.post(url, headers=headers, json=form) as response:
        _debug_response(response, logger)
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


def _get_challenge_pair():
    code = ''.join(random.choices(CHARS, k=112))
    sha = hashlib.sha256()
    sha.update(code.encode())
    challenge = base64.b64encode(sha.digest(), altchars=b'-_').decode().replace('=', '')
    return code, challenge


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


def _debug_response(response, logger):
    if not logging.is_debug_enabled():
        return
    logger.debug(('=' * 80))
    logger.debug('_debug_response(response)')
    if response.request_info.method == 'POST':
        for name, obj in (('response', response), ('response.request_info', response.request_info),):
            logger.debug(name)
            for attr in dir(obj):
                if attr.startswith('_'):
                    continue
                val = repr(getattr(obj, attr))
                val = val[:200] if len(val) > 200 else val
                val = val.replace('\n', '\\n')
                logger.debug(f'{attr: <30} {val}')
            logger.debug(f'end of {name}')
            logger.debug('')
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
