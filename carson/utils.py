
import json
from datetime import datetime, timedelta, timezone

_ONE_YEAR_MILLIS = timedelta(days=365).total_seconds() * 1000


class JSONEncoderHelper(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            if not obj.tzinfo:
                obj = datetime.fromtimestamp(obj.timestamp(), tz=timezone.utc)
            return obj.isoformat(timespec='microseconds')
        if hasattr(obj, 'dump') and callable(obj.dump):
            return obj.dump()
        return super().default(obj)


def _json_timestamp_decoder(obj):
    for attr in ('timestamp', 'scheduled_charging_start_time', 'gps_as_of'):
        if attr in obj:
            val = obj.get(attr)
            if (not isinstance(val, int) and not isinstance(val, float)) or val <= 0:
                val = None
            else:
                val = val / 1000 if val > _ONE_YEAR_MILLIS else val
                val = datetime.fromtimestamp(val, tz=timezone.utc)
            obj[attr] = val
    return obj


def json_loads(txt):
    return json.loads(txt, object_hook=_json_timestamp_decoder)


def json_dumps(obj, *args, **kwargs):
    kwargs['cls'] = JSONEncoderHelper
    return json.dumps(obj, *args, **kwargs)
