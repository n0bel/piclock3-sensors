"""Are sensors found and read the way the kernel lays them out, does the
line say what the template asks, and do the conditions come out right?

    python3 tests/devicestest.py

The sensors are folders made up in a temporary directory, shaped like
/sys/bus/w1/devices, /sys/class/hwmon and /sys/bus/iio/devices, so this
runs on any machine.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
# PiClock3, for the overlay's sums: two folders up when this is cloned into
# plugins/, or a checkout beside this one
for where in (os.path.join(HERE, '..', '..'), os.path.join(HERE, '..',
                                                           'PiClock3')):
    if os.path.isdir(os.path.join(where, 'PiClock3')):
        sys.path.insert(1, os.path.abspath(where))
        break

import devices  # noqa: E402
from PiClock3.Weather import Weather  # noqa: E402

# folder, file, contents - under w1/, hwmon/ and iio/
FILES = [
    ('w1/28-0000058e0f0c', 'temperature', '22500\n'),
    ('w1/28-0000031b54e7', 'w1_slave',
     '72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n'
     '72 01 4b 46 7f ff 0e 10 57 t=23125\n'),
    ('w1/28-000000000bad', 'w1_slave',
     '72 01 4b 46 7f ff 0e 10 57 : crc=00 NO\n'
     '72 01 4b 46 7f ff 0e 10 57 t=23125\n'),
    ('w1/28-0000000085aa', 'temperature', '85000\n'),
    ('w1/10-000802b4d2a3', 'temperature', '-4250\n'),
    # a 1-Wire part that is not a thermometer
    ('w1/2d-00000041b1a3', 'eeprom', ''),

    # the Pi's own, as the rig shows it
    ('hwmon/hwmon0', 'name', 'cpu_thermal\n'),
    ('hwmon/hwmon0', 'temp1_input', '35537\n'),
    # a voltage monitor, which has nothing here to read
    ('hwmon/hwmon1', 'name', 'rpi_volt\n'),
    ('hwmon/hwmon1', 'in0_lcrit_alarm', '0\n'),
    ('hwmon/hwmon2', 'name', 'sht3x\n'),
    ('hwmon/hwmon2', 'temp1_input', '21875\n'),
    ('hwmon/hwmon2', 'humidity1_input', '48300\n'),
    ('hwmon/hwmon2', 'temp1_max', '60000\n'),

    # processed readings: thousandths, and kilopascals
    ('iio/device0', 'name', 'bme280\n'),
    ('iio/device0', 'in_temp_input', '22340\n'),
    ('iio/device0', 'in_humidityrelative_input', '45678\n'),
    ('iio/device0', 'in_pressure_input', '98.765\n'),
    ('iio/device0', 'in_temp_oversampling_ratio', '2\n'),
    # raw ones, by their own scale and a shared one with an offset
    ('iio/device1', 'name', 'skyprobe\n'),
    ('iio/device1', 'in_temp_object_raw', '13000\n'),
    ('iio/device1', 'in_temp_object_scale', '0.5\n'),
    ('iio/device1', 'in_temp_ambient_raw', '1000\n'),
    ('iio/device1', 'in_temp_scale', '10\n'),
    ('iio/device1', 'in_temp_offset', '1200\n'),
    # both forms of one channel: the processed one is used
    ('iio/device2', 'name', 'both\n'),
    ('iio/device2', 'in_temp_raw', '99999\n'),
    ('iio/device2', 'in_temp_input', '18000\n'),
]


def close(a, b):
    return a is not None and abs(a - b) < 1e-6


def show(quantity, value):
    return {'temperature': '%.1fC', 'humidity': '%.0f%%',
            'pressure': '%.0fmb'}[quantity] % value


def cases(root):
    found = devices.probes(os.path.join(root, 'w1'),
                           os.path.join(root, 'hwmon'),
                           os.path.join(root, 'iio'))

    def value(key):
        return found[key].read()

    return [
        ('every thermometer on 1-Wire is found, named w1- and its folder',
         sorted(k for k in found if k.startswith('w1-'))
         == sorted('w1-' + f[0][3:] for f in FILES[:5])),
        ('a 1-Wire part that is not a thermometer is left out',
         'w1-2d-00000041b1a3' not in found),
        ('temperature is thousandths of a degree',
         value('w1-28-0000058e0f0c') == 22.5),
        ('w1_slave is read when temperature is not there',
         value('w1-28-0000031b54e7') == 23.125),
        ('a failed check gives no reading',
         value('w1-28-000000000bad') is None),
        ('85 degrees exactly is a probe that has not read yet',
         value('w1-28-0000000085aa') is None),
        ('below freezing reads below freezing',
         value('w1-10-000802b4d2a3') == -4.25),
        ('hwmon: the Pi\'s own temperature',
         close(value('hwmon-cpu_thermal-temp1'), 35.537)),
        ('hwmon: a sensor\'s temperature and humidity, each its quantity',
         close(value('hwmon-sht3x-temp1'), 21.875)
         and found['hwmon-sht3x-temp1'].quantity == 'temperature'
         and close(value('hwmon-sht3x-humidity1'), 48.3)
         and found['hwmon-sht3x-humidity1'].quantity == 'humidity'),
        ('hwmon: limits and voltages are not readings',
         not any(k.startswith('hwmon-rpi_volt') or k.endswith('max')
                 for k in found)),
        ('iio: temperature, humidity and pressure in C, % and mb',
         close(value('iio-bme280-temp'), 22.34)
         and close(value('iio-bme280-humidity'), 45.678)
         and close(value('iio-bme280-pressure'), 987.65)
         and found['iio-bme280-pressure'].quantity == 'pressure'),
        ('iio: settings beside the readings are not readings',
         'iio-bme280-temp-oversampling' not in found),
        # the kernel's rule: an offset with no channel applies to them all
        ('iio: a raw reading by its own scale, after the shared offset',
         close(value('iio-skyprobe-temp-object'), 7.1)),
        ('iio: a raw reading by a shared scale, after its offset',
         close(value('iio-skyprobe-temp-ambient'), 22.0)),
        ('iio: the processed reading where there are both',
         close(value('iio-both-temp'), 18.0)),
        ('a sensor whose file is gone gives no reading',
         devices.readScaled(os.path.join(root, 'gone'), 1) is None),

        ('empty, the line is each name and its reading',
         devices.line('', ['Inside', 'Outside'],
                      {'Inside': ('temperature', 22.5),
                       'Outside': ('temperature', -4.25)}, show)
         == 'Inside 22.5C   Outside -4.2C'),
        ('a template puts each reading where its name is, in its units',
         devices.line('In {Inside}, {Damp}, {Air}',
                      ['Inside', 'Damp', 'Air'],
                      {'Inside': ('temperature', 22.5),
                       'Damp': ('humidity', 48.3),
                       'Air': ('pressure', 1013.2)}, show)
         == 'In 22.5C, 48%, 1013mb'),
        ('a sensor with no reading shows --',
         devices.line('{Inside}', ['Inside'], {}, show) == '--'),
        ('a name that is no sensor is left for the clock',
         devices.line('{Inside} at {location.latitude}', ['Inside'],
                      {'Inside': ('temperature', 20.0)}, show)
         == '20.0C at {location.latitude}'),

        ('our temperature stands in for theirs, and the rest is theirs',
         overlaid['temp'] == 10.0 and overlaid['icon'] == 'cloudy'
         and overlaid['wind'] == 15 and overlaid['dew'] == 5.0
         and overlaid['pressure'] == 1013.0),
        ('humidity is worked out again from their dew point',
         close(overlaid['humidity'], Weather.humidity(10.0, 5.0))),
        ('so is feels-like',
         overlaid['feels-like']
         == Weather.feelsLikeFromDewpoint(10.0, 5.0, 15)),
        ('our humidity is used where we have one, and the dew point from it',
         close(both['humidity'], 70.0)
         and close(both['dew'], Weather.dewPoint(10.0, 70.0))),
        ('our pressure stands in for theirs',
         devices.overlay(THEIRS, {'pressure': 990.0})['pressure'] == 990.0),
        ('a provider with humidity and no dew point still gets one',
         close(devices.overlay({'temp': 20.0, 'humidity': 50.0},
                               {'temp': 20.0})['dew'],
               Weather.dewPoint(20.0, 50.0))),
        ('with neither, their humidity and feels-like are dropped',
         devices.overlay({'temp': 20.0, 'humidity': None,
                          'feels-like': 19.0}, {'temp': 15.0})
         == {'temp': 15.0}),
        ('with no provider, just ours',
         devices.overlay(None, {'temp': 12.5}) == {'temp': 12.5}),
        ('with no readings, theirs as they are',
         devices.overlay(THEIRS, {'temp': None}) == THEIRS),
        ('with neither, nothing',
         devices.overlay(None, {}) is None),
    ]


# what a station might report: Celsius, km/h, millibars
THEIRS = {'temp': 12.0, 'dew': 5.0, 'humidity': 62.0, 'wind': 15,
          'pressure': 1013.0, 'icon': 'cloudy', 'feels-like': 10.5}
overlaid = devices.overlay(THEIRS, {'temp': 10.0})
both = devices.overlay(THEIRS, {'temp': 10.0, 'humidity': 70.0})


def main():
    root = tempfile.mkdtemp()
    try:
        for folder, leaf, text in FILES:
            os.makedirs(os.path.join(root, folder), exist_ok=True)
            with open(os.path.join(root, folder, leaf), 'w') as fh:
                fh.write(text)
        results = cases(root)
    finally:
        shutil.rmtree(root)
    failed = 0
    for name, ok in results:
        failed += not ok
        print('  %s  %s' % ('ok  ' if ok else 'FAIL', name))
    print('%d cases, %d failed' % (len(results), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
