# Streaming

/ [`carson`](../README.md) / docs / streaming.md

> More detailed examples and considerations will follow shortly.

Tesla provides a `websocket` endpoint from which telemetry data can be streamed and stored.  To
begin streaming this telemetry, issue the following command.

```
> carson -v --name YOUR_CAR_NAME --stream
```

If there is no user present, you will see something similar to the following:

```
$ carson --name photon --stream
Streamer task ending. car='online'. user_present=False shift_state=None waypoints=0
```

`carson` will attempt to *wake-up* the car and initiate the streaming telemetry.  By default, the telemetry simply
outputs the data to log.  A sample of that output is below.

```
2020-01-01 14:09:30,129 D carson  Req# 1:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles' status=200 duration=0:00:00.435516
2020-01-01 14:09:30,752 D carson  Req# 2:  Method=POST url='https://owner-api.teslamotors.com/api/1/vehicles/1234567890123456/wake_up' status=200 duration=0:00:00.614805
2020-01-01 14:09:30,752 D carson  Waiting for car to wake up.
2020-01-01 14:09:37,920 D carson  Req# 9:  Method=GET url='https://owner-api.teslamotors.com/api/1/vehicles/1234567890123456/vehicle_data' status=200 duration=0:00:00.301021
2020-01-01 14:09:37,920 I carson  Streaming iteration=1
2020-01-01 14:09:37,961 I carson  car=Vehicle('Dark Nebula' state='online' miles=18,421 software='2019.40.50.5' battery_level=81) iteration=1  client_errors=0 vehicle_disconnects=0
2020-01-01 14:09:38,412 D carson  {"msg_type":"data:subscribe","token":"bWlj********NmY1","value":"speed,odometer,soc,elevation,est_heading,est_lat,est_lng,power,shift_state,range,est_range,heading","tag":"0123456789"}
2020-01-01 14:09:38,412 D carson  msg_count=1 msg={'msg_type': 'control:hello', 'connection_timeout': 0}
2020-01-01 14:09:39,474 D carson  msg_count=2 msg={'msg_type': 'data:update', 'tag': '0123456789', 'value': '1577909378751,,18421.1,81,232,182,40.778955,-73.968583,0,,242,223,8'}
2020-01-01 14:09:49,479 D carson  Timeout waiting for next message.
2020-01-01 14:09:49,495 D carson  msg_count=3 msg={'msg_type': 'data:error', 'tag': '0123456789', 'value': 'disconnected', 'error_type': 'vehicle_disconnected'}
2020-01-01 14:09:49,566 I carson  Streamer task ending due to shift state=''.
```
