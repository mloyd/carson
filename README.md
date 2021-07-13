
# carson

[![Latest Version][pypi-image]][pypi-url]

* [Overview](#overview)
* [States And Commands](#states-and-commands)
* [Configuration](#configuration)
* [Streaming](#streaming)
* [Pythonic Features](#features)

## Overview

`carson` is a simple Python interface for Tesla's unofficial JSON API and includes some utilities to work with data it
generates.  Lots of work to discover and document the API was done by Tim Dorr and dozens of contributors to his
[tesla-api](https://github.com/timdorr/tesla-api) project as well as Mark Seminatore and
[TeslaJS](https://github.com/mseminatore/TeslaJS).  So, thanks to them for the head start.

Among the goals for this project is to have an [`asyncio`](https://docs.python.org/3/library/asyncio.html) based
library.  As a result, Python 2 is not supported.  In fact, it seems like it has been a decade since the *provisional*
tag was removed from the `asyncio` library because it has evolved so much.  There are many guides, articles, and posts
based on early features of `asyncio`.  The best way to stay up to date is by starting with Python's documentation at
[https://docs.python.org/library/asyncio.html](https://docs.python.org/library/asyncio.html).  This project uses the
`async`/`await` syntax introduced in [PEP-492](https://www.python.org/dev/peps/pep-0492/).  As of this writing, the
latest version of Python is 3.8.1.

### Dependencies

There is one dependency for basic usage &mdash; [`aiohttp`](https://docs.aiohttp.org/).

## Authentication

Tesla has made authentication a moving target.  It's a bit like playing whack-a-mole.  Understandably so because
security should always be job zero in any computing effort.  And all 3rd party libraries not developed by Tesla are
unofficial.  Perhaps this recent variability is a sign of an impending App Store?  I don't know... just speculating.
But _authentication_ is not a goal of this library.

Below are a few mechanisms to try to successfully authenticate.  Your results may vary depending on a number of factors.
Like most network service based apps, Tesla employ's DNS traffic policies with weighted and geo values (among others)
which means you might or might not be presented with captcha during password authentication.

### BYOT

The easiest and most reliable method is to bring your own access token.  Both the command line utility and `Session`
class accept an access token instead of email/password.  If you want to use environment variables or a configuration
file to supply your access token, see the [configuration](#configuration) section below for more information.

### Email & Password

Both the command line utility and `Session` class will accept `email` and `password` arguments.  They will be used to
generate an access token.  Examples include:

```console
> python -m carson --email nikola@tesla.com --password electricity --list
Car #1 Vehicle('Antares' state='asleep' id=123..789)
Car #2 Vehicle('Dark Nebula' state='asleep' id=321..987)
```
A better practice to keep from leaking your password into your shell history is to leave `--password` off and let the
command line utility securely prompt you for it.  Example:

```console
> python -m carson --email nikola@tesla.com --list
Password for nikola@tesla.com:
Car #1 Vehicle('Antares' state='asleep' id=123..789)
Car #2 Vehicle('Dark Nebula' state='asleep' id=321..987)
```

### Generate Your Own

The command line utility can be used to generate an access token that you can then save securely for future use.  Add
the `--token-only` option as show below:
```console
> python -m carson --email nikola@tesla.com --token-only
Password for nikola@tesla.com:
{
  "access_token": "qts-0a1b2c...5f0a1b",
  "token_type": "bearer",
  "expires_in": 3888000,
  "refresh_token": "b1a0f5...c2b1a0",
  "created_at": 1626183175
}
```

your own Credentials can be provided and `carson` will attempt to create an access token for you.

If you already have (or know how to generate) an `access_token` or simply do not want to provide your Tesla account's
email and password, you can instead provide your token.  Simply replace the arguments `email` and `password` passed to
the `Session` constructor with the argument `access_token` (or `--access-token` if using the command line).  Your token
should resemble a long list of characters similar to `qts-0a1b2c...5f0a1b`.

Example:
```python
...
async with Session(access_token='qts-0a1b2c...5f0a1b') as session:
...
```

## States And Commands

With its most basic usage, you can use `carson` to get the current state of car with the following code:

```python
>>>import asyncio
>>>from carson import Session
>>>async def main():
...    name = 'Dark Nebula'
...    async with Session(email='nikola@tesla.com', password='electricity') as session:
...        car = await session.vehicles(name)
...        print(f'{name} is {car.state!r}')

>>>asyncio.run(main())
Dark Nebula is 'asleep'
```

Or you can run it from the command line in a similar fashion:
```console
> python -m carson -v --email nikola@tesla.com --password electricity --display-name "Dark Nebula"
```

To get a sense of what is happening, you can add verbose and see the requests being made.
```console
> python -m carson -v --email nikola@tesla.com --password electricity --display-name "Dark Nebula"
2020-01-01 10:45:59,418 D carson  Performing OAuth password grant for email='nikola@tesla.com'
2020-01-01 10:46:00,229 D carson  Req# 1:  Method=POST url='https://owner-api.teslamotors.com/oauth/token?grant_type=password' status=200 duration=0:00:00.810031
2020-01-01 10:46:00,943 D carson  Req# 2:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles' status=200 duration=0:00:00.712868
2020-01-01 10:46:00,944 I carson  Vehicle('Dark Nebula' state='asleep')
```

You can see that two requests are made:

  1.  First is to generate an `oauth` token which is required for all subsequent requests.
  2.  Get a list of vehicles associated with the credentials provided.

## Configuration

Credentials can also be stored in configuration.  `carson` looks for credentials in the following order:

1.  The arguments `email` and `password` passed to the `Session` constructor.
2.  The argument `access_token` passed to the `Session` constructor.
3.  The environment variables `CARSON_EMAIL`, `CARSON_PASSWORD`, `CARSON_ACCESS_TOKEN`.
4.  An `.ini` style config file named `.carson` or `carson.ini` in the user's home directory.

> **Regarding credentials:** Always use care when storing credentials.  Sometimes
> [bad things](https://www.diogomonica.com/2017/03/27/why-you-shouldnt-use-env-variables-for-secret-data/)
> can happen and often time will.

### Credential Precedence

Credentials (`password` and `access_token`) are used in the following order of precedence.  When reading _'if'_ and
_'if not'_, think Python boolean operations (e.g. `''`, `None`, `0` are all `False`).

1.  If `password` is given to the `Session` constructor, it will always be used to generate a new access token.  Even if
    a valid `access_token` is given to the `Session` constructor at the same time.  This means a value for `email` must
    also be given (or implied from config).
2.  If `password` is not given to the `Session` constructor, the value used for `access_token` is used.  Or, if not
    given, implied from config.
3.  If neither `password` nor `access_token` are given to the `Session` constructor, but both `password` and
    `access_token` are defined in config, the `access_token` from config will be used.

## Streaming

Tesla provides a `websocket` endpoint from which telemetry data can be streamed and stored.  To begin streaming this
telemetry, issue the following command.

```console
> python -m carson -v --display-name YOUR_CAR_NAME --stream
```

`carson` will attempt to _wake-up_ the car and initiate the streaming telemetry.  By default, the telemetry simply
outputs the data to log.  A sample of that output is below.

```console
2020-01-01 14:09:30,129 D carson  Req# 1:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles' status=200 duration=0:00:00.435516
2020-01-01 14:09:30,752 D carson  Req# 2:  Method=POST url='https://owner-api.teslamotors.com/api/1/vehicles/01234567890123456/wake_up' status=200 duration=0:00:00.614805
2020-01-01 14:09:30,752 D carson  Waiting for car to wake up.
2020-01-01 14:09:37,920 D carson  Req# 9:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles/01234567890123456/vehicle_data' status=200 duration=0:00:00.301021
2020-01-01 14:09:37,920 I carson  Streaming iteration=1
2020-01-01 14:09:37,961 I carson  car=Vehicle('Dark Nebula' state='online' miles=18,421 software='2019.40.50.5' battery_level=81) iteration=1  client_errors=0 vehicle_disconnects=0
2020-01-01 14:09:38,412 D carson  {"msg_type":"data:subscribe","token":"bWlj********NmY1","value":"speed,odometer,soc,elevation,est_heading,est_lat,est_lng,power,shift_state,range,est_range,heading","tag":"0123456789"}
2020-01-01 14:09:38,412 D carson  msg_count=1 msg={'msg_type': 'control:hello', 'connection_timeout': 0}
2020-01-01 14:09:39,474 D carson  msg_count=2 msg={'msg_type': 'data:update', 'tag': '0123456789', 'value': '1577909378751,,18421.1,81,232,182,40.778955,-73.968583,0,,242,223,8'}
2020-01-01 14:09:49,479 D carson  Timeout waiting for next message.
2020-01-01 14:09:49,495 D carson  msg_count=3 msg={'msg_type': 'data:error', 'tag': '0123456789', 'value': 'disconnected', 'error_type': 'vehicle_disconnected'}
2020-01-01 14:09:49,566 I carson  Streamer task ending due to shift state=''.
```

## Pythonic Features

Python is a fantastic language.  One of my favorite features is its ability to customize attribute access.  That ability
allows a _Vehicle_ class instance to basically act like a chameleon.  As Tesla changes its data structure and command
interface for its cars, it's pretty easy for a Python class to essentially keep itself up to date.

This section would normally be placed after the [States And Commands](#states-and-commands) section.  But I wanted to
put this above the fold to call out the Pythonic features of `carson` - both in programmability and general use on the
command line.

### Recursive Dot-Notation

Consider this JSON response from Tesla when getting making a call to `vehicle_data`:
```json
{
  "response": {
    "id": 98765432109876543,
    "vehicle_id": 1234567890,
    "display_name": "Dark Nebula",
    "state": "online",
    ...
    "vehicle_state": {
      "api_version": 7,
      ...
      "sentry_mode": false,
      "sentry_mode_available": true,
      "smart_summon_available": true,
      "software_update": {
        "download_perc": 0.85279,
        "expected_duration_sec": 2700,
        "install_perc": 0,
        ...
```

With `carson`, after you make the call to get the vehicle data, you can access the JSON response that is returned, or
simply reference its associated JSON path on the instance of the `Vehicle` using standard Python dot-notation like this:

```python
car = await my_session.vehicles('Dark Nebula')
json_response = await car.vehicle_data()

# I have options here.  I can access the JSON data as a normal Python `dict`
perc = json_response['vehicle_state']['software_update']['download_perc']

# Or as a Python attribute
perc = car.vehicle_state.software_update.download_perc

if 0 < perc < 1:
    print(f'Downloading: {perc:.2%} complete.')
else:
    print('Download complete' if perc == 1 else 'N/A')
```

### Endpoint Commands As `await`able Attributes

Similarly, commands can that are mapped to an endpoint accessed via Python's class instance attribute mechanism will
return an `await`able coroutine.  For example, the `Vehicle` class in `carson` does not have an attribute named
`start_charge`.  The endpoints mapping, however, does map `START_CHARGE` to a POST request to the URI
`api/1/vehicles/{vehicle_id}/command/charge_start`.  This makes it possible to start charging your Tesla with either
this code:

```python
car = await my_session.vehicles('Dark Nebula')
await car.start_charge()
```

or this command

```console
> python -m carson -v --command start_charge
2020-01-01 11:51:44,349 D carson  Req# 1:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles' status=200 duration=0:00:02.460019
2020-01-01 11:51:44,350 I carson  Vehicle('Dark Nebula' state='online')
2020-01-01 11:51:44,350 I carson  Performing 'start_charge'...
2020-01-01 11:51:44,753 D carson  Req# 2:  Method=POST url='https://owner-api.teslamotors.com/api/1/vehicles/01234567890123456/command/charge_start' status=200 duration=0:00:00.403062
2020-01-01 11:51:44,754 I carson  Result=
{'carsonRequest': {'method': 'POST',
                   'url': 'https://owner-api.teslamotors.com/api/1/vehicles/01234567890123456/command/charge_start'},
 'carsonTimestamp': '2020-01-01T17:51:44.350726',
 'error': None,
 'error_description': '',
 'response': {'reason': 'complete', 'result': True},
 'status': 200}
```

[pypi-image]: https://img.shields.io/pypi/v/carson.svg
[pypi-url]: https://pypi.org/project/carson/
