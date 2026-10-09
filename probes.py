"""Print each sensor the Pi has found, as the config names it.

    python3 plugins/Sensors/probes.py

Copy the ones you want under probes:, each with a name for the clock to
show.  Warming a sensor in your hand is how to tell two apart.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import devices  # noqa: E402


UNIT = {'temperature': '%.1f°C', 'humidity': '%.0f%%',
        'pressure': '%.1f mb'}


def main():
    found = devices.probes()
    if not found:
        sys.exit('No sensors found.  Add the overlay for yours to'
                 ' config.txt and reboot - see the README.')
    width = max(len(key) for key in found)
    for key, sensor in found.items():
        value = sensor.read()
        reading = ('no reading' if value is None
                   else UNIT[sensor.quantity] % value)
        print('%-*s   %s' % (width, key, reading))


if __name__ == '__main__':
    main()
