
"""
Lots of possibilities here.  Just not right now.
"""

import os
from . import config, utils


CAR_STATUS_PATH = None
CAR_STREAM_PATH = None


def record_vehicle_status(data):
    global CAR_STATUS_PATH

    if not CAR_STATUS_PATH:
        CAR_STATUS_PATH = os.path.join(config.get('data_root'), 'vehicle.data')

    with open(CAR_STATUS_PATH, 'a') as writer:
        writer.write(f'{utils.json_dumps(data)}\n')


def record_waypoint(vehicle_id, data):
    global CAR_STREAM_PATH

    if not CAR_STREAM_PATH:
        CAR_STREAM_PATH = os.path.join(config.get('data_root'), f'stream.data.{vehicle_id}')

    with open(CAR_STREAM_PATH, 'a') as writer:
        writer.write(f'{vehicle_id},{data}\n')
