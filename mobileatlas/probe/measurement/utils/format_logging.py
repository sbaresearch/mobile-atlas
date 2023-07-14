# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

#import json
#import jsonpickle
import jsons

jsons.suppress_warning("datetime-without-tz")

def format_extra(event_name, params = None):
    extra={'event': event_name}
    if params:
        #json_str = jsonpickle.encode(params, unpicklable=False) #json.dumps(params, default=str)
        #extra['params'] = json.loads(json_str)
        extra['params'] = jsons.dump(params)
    return extra