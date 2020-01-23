
import json
from datetime import datetime, timedelta

_ONE_YEAR_MILLIS = timedelta(days=365).total_seconds() * 1000
_1970 = datetime(1900, 1, 1)


class JSONEncoderHelper(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            if obj < _1970:
                return 0
            return int((obj - _1970).total_seconds() * 1000)
        return super().default(obj)


def _json_timestamp_decoder(obj):
    for attr in ('timestamp', 'scheduled_charging_start_time', 'gps_as_of'):
        if attr in obj:
            val = obj.get(attr)
            if (not isinstance(val, int) and not isinstance(val, float)) or val <= 0:
                val = None
            else:
                delta = timedelta(seconds=val) if val < _ONE_YEAR_MILLIS else timedelta(milliseconds=val)
                val = datetime(1970, 1, 1) + delta
            obj[attr] = val
    return obj


def json_loads(txt):
    return json.loads(txt, object_hook=_json_timestamp_decoder)


def json_dumps(obj):
    return json.dumps(obj, cls=JSONEncoderHelper)
