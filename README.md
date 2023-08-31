
# carson

[![Latest Version][pypi-image]][pypi-url]

* [Overview](#overview)
* [Installation](#installation)
* [Authentication](#authentication)
* [States And Commands](#states-and-commands)
* [Examples](#examples)
* [Streaming](#examples)

## Overview

`carson` is a simple Python interface for Tesla's unofficial JSON API and includes some utilities to work with data it
generates.  Lots of work to discover and document the API was done by Tim Dorr and dozens of contributors to his
[tesla-api](https://github.com/timdorr/tesla-api) project as well as Mark Seminatore and
[TeslaJS](https://github.com/mseminatore/TeslaJS).  So, thanks to them for the head start.

Among the goals for this project is to have an [`asyncio`](https://docs.python.org/3/library/asyncio.html) based
library.  As a result, Python 2 is not supported.  In fact, it seems like it has been a decade since the *provisional*
tag was removed from the `asyncio` library because it has evolved so much.  There are many guides, articles, and posts
based on early features of `asyncio`.  The best way to stay up to date is by starting with Python's standard library
documentation for [`asyncio`](https://docs.python.org/3/library/asyncio.html).

### Dependencies

There is one dependency for basic usage &mdash; [`aiohttp`](https://docs.aiohttp.org/).

## Installation

As with most python projects, you should create an isolated python environment.  The following
example will use Python's `venv` module.  But you can use any virtual environment manager you wish
(e.g. pipenv, poetry, virtualenv, conda).

### Windows

```
python3.exe -m venv .venv
.venv\Scripts\activate
python -m pip install "carson[jwt]"
carson --version
carson/1.2.1+0d5c31d
```

### Linux/Mac

```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "carson[jwt]"
carson --version
carson/1.2.1+0d5c31d
```

For command line usage, `carson` can be invoked either as a Python module `python -m carson` or as a
script (simply named `carson`) which gets created during installation.  Both invoke the same entry
point essentially making the following two statements the same.

```
python -m carson --version
```

is equivalent to

```
carson --version
```

## Authentication

This project is *BYOT* (bring your own token) only.  OAuth and authentication flows are _**not**_
goals of this project.   There are many apps and utilities that provide this if you need help
creating access and/or refresh tokens to use Tesla's API.

At a minimum, an **access token** is required.  This can be set with the environment variable named
`CARSON_ACCESS_TOKEN` or passed to the `carson.Session` constructor.  Values passed as arguments
take priority over environment variables.

If you want `carson` to refresh expired access tokens, you will also need to supply a valid
**refresh token** that matches the supplied **access token**.  Likewise, this can be set as an
environment variable `CARSON_REFRESH_TOKEN` or passed to the `carson.Session` constructor.

You can register a callable (e.g. function, lambda, callable object, etc.) to be invoked when tokens
have refreshed.  This _callable_ should take one positional argument which will be a `dict` and
contain the tokens that have updated.

See [`docs/examples.md`](docs/examples.md) for more examples.

## States And Commands

With its most basic usage, you can use `carson` to get the current state of car with the following:

```python
>>>import asyncio
>>>from carson import Session
>>>async def main():
...    async with Session() as session:
...        car = await session.vehicle
...        print(f'{car.name} is {car.state!r}')

>>>asyncio.run(main())
Dark Nebula is 'asleep'
```

From the command line, you can invoke `carson --list` to get a list of vehicles associated with the
access token you are using:

```
$ carson --list
Car #1 Vehicle('Dark Nebula' state='asleep' id=1234567890123456)
Car #2 Vehicle('photon' state='online' id=1234567890123456)
```

If you have more than one vehicle and want to specify which car to show, you can pass `--name` to disambiguate which car
you want to show.

```
carson --name photon
Vehicle('photon' state='online' miles=52,809 software='2023.7.30' battery_level=72)
```

To get a sense of what is happening, you can increase verbosity and see the requests being made.

```
carson -v --name photon
2023-08-31 11:54:44,615 D carson  Req 1 GET /api/1/vehicles HTTP/1.1 200 OK
2023-08-31 11:54:44,929 D carson  Req 2 GET /api/1/vehicles/1234567890123456/vehicle_data HTTP/1.1 200 OK
2023-08-31 11:54:44,929 I carson  Vehicle('photon' state='online' miles=52,809 software='2023.7.30' battery_level=72)
```

Further increasing the verbosity will produce more detailed output.

```
$ carson -vv --name photon
2023-08-31 11:56:52,296 D carson  Req 1 status=200 dur=0:00:00.131960
2023-08-31 11:56:52,297 D carson  GET https://owner-api.teslamotors.com/api/1/vehicles
2023-08-31 11:56:52,297 D carson  < Host: owner-api.teslamotors.com
2023-08-31 11:56:52,297 D carson  < User-Agent: carson/1.2.1+0d5c31d
2023-08-31 11:56:52,297 D carson  < Accept: application/json
2023-08-31 11:56:52,297 D carson  < Authorization: Bearer e***ng
2023-08-31 11:56:52,297 D carson  < Accept-Encoding: gzip, deflate
2023-08-31 11:56:52,297 D carson
2023-08-31 11:56:52,297 D carson  HTTP 200 OK HttpVersion(major=1, minor=1)
2023-08-31 11:56:52,297 D carson  > x-xss-protection: 1; mode=block
2023-08-31 11:56:52,298 D carson  > Content-Type: application/json; charset=utf-8
2023-08-31 11:56:52,298 D carson  > Vary: Accept
2023-08-31 11:56:52,298 D carson  > Content-Length: 416
2023-08-31 11:56:52,298 D carson  > x-envoy-upstream-service-time: 97
2023-08-31 11:56:52,298 D carson  > x-envoy-upstream-cluster: owner-api
2023-08-31 11:56:52,298 D carson  > x-frame-options: DENY
2023-08-31 11:56:52,298 D carson  > x-content-type-options: nosniff
2023-08-31 11:56:52,298 D carson  > strict-transport-security: max-age=31536000; includeSubDomains
2023-08-31 11:56:52,298 D carson  > Cache-Control: no-cache, no-store, private, s-max-age=0
2023-08-31 11:56:52,298 D carson  > Date: Thu, 31 Aug 2023 16:56:52 GMT
2023-08-31 11:56:52,298 D carson  > Server: envoy
2023-08-31 11:56:52,298 D carson
2023-08-31 11:56:52,298 D carson  response={'count': 1, 'response': [{'id': 1234567890123456, 've...
2023-08-31 11:56:52,299 D carson
2023-08-31 11:56:52,600 D carson  Req 2 status=200 dur=0:00:00.300726
2023-08-31 11:56:52,600 D carson  GET https://owner-api.teslamotors.com/api/1/vehicles/1234567890123456/vehicle_data
2023-08-31 11:56:52,600 D carson  < Host: owner-api.teslamotors.com
2023-08-31 11:56:52,600 D carson  < User-Agent: carson/1.2.1+0d5c31d
2023-08-31 11:56:52,600 D carson  < Accept: application/json
2023-08-31 11:56:52,600 D carson  < Authorization: Bearer e***ng
2023-08-31 11:56:52,600 D carson  < Accept-Encoding: gzip, deflate
2023-08-31 11:56:52,600 D carson
2023-08-31 11:56:52,600 D carson  HTTP 200 OK HttpVersion(major=1, minor=1)
2023-08-31 11:56:52,600 D carson  > x-xss-protection: 1; mode=block
2023-08-31 11:56:52,600 D carson  > Content-Type: application/json; charset=utf-8
2023-08-31 11:56:52,600 D carson  > Vary: Accept
2023-08-31 11:56:52,601 D carson  > Content-Length: 7047
2023-08-31 11:56:52,601 D carson  > x-envoy-upstream-service-time: 298
2023-08-31 11:56:52,601 D carson  > x-envoy-upstream-cluster: owner-api-vehicle-data
2023-08-31 11:56:52,601 D carson  > x-frame-options: DENY
2023-08-31 11:56:52,601 D carson  > x-content-type-options: nosniff
2023-08-31 11:56:52,601 D carson  > strict-transport-security: max-age=31536000; includeSubDomains
2023-08-31 11:56:52,601 D carson  > Cache-Control: no-cache, no-store, private, s-max-age=0
2023-08-31 11:56:52,601 D carson  > Date: Thu, 31 Aug 2023 16:56:52 GMT
2023-08-31 11:56:52,601 D carson  > Server: envoy
2023-08-31 11:56:52,601 D carson
2023-08-31 11:56:52,601 D carson  response={'response': {'id': 1234567890123456, 'user_id': 123456...
2023-08-31 11:56:52,602 D carson
2023-08-31 11:56:52,602 I carson  Vehicle('photon' state='online' miles=52,809 software='2023.7.30' battery_level=72)
```

From this point, you can imagine any kind of state query or command supported by Tesla's API can be queried or invoked.

```
carson --command wake_up
carson --command door_lock
```

> Note: In the case of waking up a car, the command line `carson --command wake_up` is effectively
> the same as as the short hand `carson --wake-up` command.

## Pythonic Features

Python is a fantastic language.  One of my favorite features is its ability to customize attribute access.  That ability
allows a *Vehicle* class instance to basically act like a chameleon.  As Tesla changes its data structure and command
interface for its cars, it's pretty easy for a Python class to essentially keep itself up to date.

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
simply reference its associated JSON path on the instance of `Vehicle` using standard Python dot-notation like this:

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

```
> carson -v --command start_charge
2020-01-01 11:51:44,349 D carson  Req# 1:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles' status=200 duration=0:00:02.460019
2020-01-01 11:51:44,350 I carson  Vehicle('Dark Nebula' state='online')
2020-01-01 11:51:44,350 I carson  Performing 'start_charge'...
2020-01-01 11:51:44,753 D carson  Req# 2:  Method=POST url='https://owner-api.teslamotors.com/api/1/vehicles/1234567890123456/command/charge_start' status=200 duration=0:00:00.403062
2020-01-01 11:51:44,754 I carson  Result=
{'carsonRequest': {'method': 'POST',
                   'url': 'https://owner-api.teslamotors.com/api/1/vehicles/1234567890123456/command/charge_start'},
 'carsonTimestamp': '2020-01-01T17:51:44.350726',
 'error': None,
 'error_description': '',
 'response': {'reason': 'complete', 'result': True},
 'status': 200}
```

## Examples

See the `docs` directory for more examples and advanced usage:

* [`docs/examples.md`](docs/examples.md)
* [`docs/streaming.md`](docs/streaming.md)

[pypi-image]: https://img.shields.io/pypi/v/carson.svg
[pypi-url]: https://pypi.org/project/carson/
