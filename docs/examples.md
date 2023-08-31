# Examples

/ [`carson`](../README.md) / docs / examples.md

In all of the following examples, a virtual environment is used and carson is installed with the
optional `jwt` dependency to allow for token validation.  See the [installation](../README.md#installation)
section for more info.

* [Tokens using environment variables](#tokens-using-environment-variables)
* [Tokens as arguments](#tokens-as-arguments)


## Tokens using environment variables

Setting environment variables with your token(s) can be used with both command line usage and with
code.  The two environment variables are `CARSON_ACCESS_TOKEN` and `CARSON_REFRESH_TOKEN` for access
token and refresh token respectively.

Only the **access token** is required for basic functionality.  If you want `carson` to **refresh**
your token as it goes along, of course, a refresh token would also be required.

### Linux/Mac

```bash
export CARSON_ACCESS_TOKEN="eyJhb...bzng"
export CARSON_REFRESH_TOKEN="eyJhb...tivw"
```

### Windows

```batch
set CARSON_ACCESS_TOKEN=eyJhb...bzng
set CARSON_REFRESH_TOKEN=eyJhb...tivw
```
### Command line

On the command line, to list of cars with the account associated with the access token:

```
carson --list
Car #1 Vehicle('photon' state='online' id=1234567981234567)
```

### Python

The same example with code.

```python
import asyncio, carson

async def main():
    async with carson.Session() as session:
        print(await session.vehicles())

asyncio.run(main())
```

Running will yield the following:

```
$ python test.py
[Vehicle('photon' state='online' id=1234567981234567)]
```

### Refreshing Tokens

It's not very helpful to have tokens refreshed on the command line.  You may see a message similar
to the following if that happens:

```
$ carson --list
Token refreshed but not stored/logged for security reasons.
Car #1 Vehicle('photon' state='online' id=1234567981234567)
```

You can handle this programmatically in Python by supplying your own callback.  Create a file named
`test.py` and add the following text:

```python
import asyncio, carson, json

def _handle_refresh(cred):
    print(f'refreshed: {json.dumps(cred, indent=2)}')

async def main():
    async with carson.Session(callback=_handle_refresh) as session:
        print(await session.car)

asyncio.run(main())
```

Running will yield the following:

```
$ python test.py
refreshed: {
  "access_token": "eyJh...4ug",
  "refresh_token": "eyJ...utQ",
  "id_token": "eyJ...oPA",
  "expires_in": 28800,
  "token_type": "Bearer",
  "created_at": 1693495357
}
Vehicle('photon' state='online' id=1234567981234567)
```

As you can see, passing in a callback to handle the new tokens allows you to store your tokens
offline however you choose (carefully, I hope).

## Tokens as arguments

You can pass tokens to `carson.Session` with arguments.  Tokens passed as arguments also take
precedence over environment variables.


### Access token

Add the following text to a file named `test.py`

```python
import asyncio, carson, json

async def main():
    async with carson.Session(access_token='eyJhb...bzng') as session:
        print(await session.car)

asyncio.run(main())
```

Running will yield the following:

```
$ python test.py
Vehicle('photon' state='online' id=1234567981234567)
```

### Refresh token

The same applies to refresh tokens when passing as arguments as when using environment variables
&dash; if you want to persist the refreshed tokens, you will need to supply a callback that can
be called when the refresh has occurred.

```python
import asyncio, carson, json

def _handle_refresh(cred):
    print(f'refreshed: {json.dumps(cred, indent=2)}')

async def main():
    access_token = 'eyJhb...bzng'
    refresh_token = 'eyJhb...tivw'
    kwargs = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'callback': _handle_refresh,
    }
    async with carson.Session(**kwargs) as session:
        print(await session.car)

asyncio.run(main())
```
