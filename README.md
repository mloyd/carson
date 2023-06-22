
# carson

[![Latest Version][pypi-image]][pypi-url]

* [Overview](#overview)
* [Authentication](#authentication)
* [Configuration](#configuration)
* [States And Commands](#states-and-commands)
* [Streaming](#streaming)

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

## Authentication

This project is *BYOT* (bring your own token) only.  OAuth 2.0 and authentication flows are **not** goals of this
project.   There are many apps and utilities that provide this if you need help creating access and/or refresh tokens to
use Tesla's API.  Refer to the [configuration](#configuration) section for information on how to use this with `carson`.

## Configuration

Tokens can be configured via environment variables or passed as arguments to the constructor.  Token values passed as
arguments take priority over environment variables.

## States And Commands

With its most basic usage, you can use `carson` to get the current state of car with the following code:

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

Or you can run it from the command line in a similar fashion:

```console
> python -m carson --name "Dark Nebula"
```

If you have more than one vehicle and want to specify which car to show, you can pass `--name` to disambiguate which car
you want to show.  Otherwise, `carson` will return the most recent vehicle listed on your account.

```console
> python -m carson --name "Dark Nebula"
```

To list all cars and their respective status, you can use `--list` to see them all.

```console
> python -m carson --list
```

To get a sense of what is happening, you can add verbose and see the requests being made.

```console
> python -m carson -v --name "Dark Nebula"
2020-01-01 10:46:00,943 D carson  Req# 2:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles' status=200 duration=0:00:00.712868
2020-01-01 10:46:00,944 I carson  Vehicle('Dark Nebula' state='asleep')
```

From this point, you can imagine any kind of state query or command supported by Tesla's API can be queried or invoked.

```console
> python -m carson --command wake_up
> python -m carson --command door_lock
```

> Note: In the case of waking up a car, the command line `python -m carson --command wake_up` is effectively the same as
as the short hand `python -m carson --wake-up` command.

## Streaming

Tesla provides a `websocket` endpoint from which telemetry data can be streamed and stored.  To begin streaming this
telemetry, issue the following command.

```console
> python -m carson -v --name YOUR_CAR_NAME --stream
```

`carson` will attempt to *wake-up* the car and initiate the streaming telemetry.  By default, the telemetry simply
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
