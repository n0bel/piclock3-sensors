"""Sensors the kernel has found, and what each one reads.

The kernel does the talking to the sensor, and shows each reading as a
small text file.  A DS18B20 appears under /sys/bus/w1, and an I2C sensor
whose driver an overlay loaded appears under /sys/class/hwmon or
/sys/bus/iio, depending on its driver.  So nothing beyond Python is
needed, whatever the chip.

Readings come out in Celsius, percent and millibars.
"""
import glob
import os
import re
from collections import namedtuple

W1 = '/sys/bus/w1/devices'
HWMON = '/sys/class/hwmon'
IIO = '/sys/bus/iio/devices'

# one reading of one sensor: what it measures, and how to read it now
Sensor = namedtuple('Sensor', 'quantity read')

NAME = re.compile(r'\{([^{}.]+)\}')

# what a sensor shows when it has no reading
MISSING = '--'

# the 1-Wire families that are thermometers: DS18S20, DS1822, DS18B20,
# DS1825 and DS28EA00
FAMILIES = ('10', '22', '28', '3b', '42')

# what a DS18B20 says before it has made a reading, and what a bad read
# often looks like.  Real rooms are seldom at exactly 85 degrees.
POWER_ON = 85.0

# hwmon's files, in thousandths of a degree and of a percent
HWMON_FILE = re.compile(r'^(temp|humidity)(\d+)_input$')

# iio's, with a channel number and modifiers such as _object: a _raw one
# is turned into units by the _offset and _scale beside it
IIO_FILE = re.compile(
    r'^in_(temp|humidityrelative|pressure)(\d*)((?:_[a-z]+)*)_(input|raw)$')

QUANTITY = {'temp': 'temperature', 'humidity': 'humidity',
            'humidityrelative': 'humidity', 'pressure': 'pressure'}

# from iio's units to Celsius, percent and millibars: thousandths of a
# degree, thousandths of a percent, and kilopascals
IIO_FACTOR = {'temperature': 0.001, 'humidity': 0.001, 'pressure': 10.0}


def probes(w1=W1, hwmon=HWMON, iio=IIO):
    """every sensor reading found, as the config names it"""
    found = {}
    found.update(oneWire(w1))
    found.update(hwmonReadings(hwmon))
    found.update(iioReadings(iio))
    return found


def oneWire(root):
    found = {}
    for family in FAMILIES:
        for folder in sorted(glob.glob(os.path.join(root, family + '-*'))):
            found['w1-' + os.path.basename(folder)] = Sensor(
                'temperature', reader(readW1, folder))
    return found


def hwmonReadings(root):
    found = {}
    for folder in sorted(glob.glob(os.path.join(root, 'hwmon*'))):
        name = chipName(folder)
        for path in sorted(glob.glob(os.path.join(folder, '*_input'))):
            match = HWMON_FILE.match(os.path.basename(path))
            if match and name:
                kind, number = match.groups()
                found['hwmon-%s-%s%s' % (name, kind, number)] = Sensor(
                    QUANTITY[kind], reader(readScaled, path, 0.001))
    return found


def iioReadings(root):
    found = {}
    # every folder, not only iio:device*: the triggers beside them have no
    # readings, and a colon is no name for a folder a test can make
    for folder in sorted(glob.glob(os.path.join(root, '*'))):
        name = chipName(folder)
        channels = {}
        for path in sorted(glob.glob(os.path.join(folder, 'in_*'))):
            match = IIO_FILE.match(os.path.basename(path))
            if match and name:
                kind, number, mods, form = match.groups()
                channel = (kind, number, mods)
                # a processed reading is the one to use where there are both
                if form == 'input' or channel not in channels:
                    channels[channel] = (path, form)
        for (kind, number, mods), (path, form) in channels.items():
            quantity = QUANTITY[kind]
            label = '%s%s%s' % ('humidity' if quantity == 'humidity' else kind,
                                number, mods.replace('_', '-'))
            factor = IIO_FACTOR[quantity]
            if form == 'input':
                read = reader(readScaled, path, factor)
            else:
                stem = os.path.join(folder, 'in_%s' % kind)
                read = reader(readRaw, path, factor,
                              shared(stem, number, mods, 'scale'),
                              shared(stem, number, mods, 'offset'))
            found['iio-%s-%s' % (name, label)] = Sensor(quantity, read)
    return found


def shared(stem, number, mods, what):
    """the _scale or _offset file for a channel: its own, or the one its
    channels share, or None"""
    for candidate in ('%s%s%s_%s' % (stem, number, mods, what),
                      '%s%s_%s' % (stem, number, what),
                      '%s_%s' % (stem, what)):
        if os.path.isfile(candidate):
            return candidate
    return None


def chipName(folder):
    try:
        with open(os.path.join(folder, 'name')) as fh:
            return fh.read().strip().replace(' ', '_')
    except OSError:
        return ''


def reader(fn, *args):
    """a reading taken when it is asked for, not when it was found"""
    return lambda: fn(*args)


def number(path):
    with open(path) as fh:
        return float(fh.read().strip())


def readScaled(path, factor):
    try:
        return number(path) * factor
    except (OSError, ValueError):
        return None


def readRaw(path, factor, scale, offset):
    try:
        raw = number(path)
        if offset:
            raw += number(offset)
        if scale:
            raw *= number(scale)
        return raw * factor
    except (OSError, ValueError):
        return None


def readW1(folder):
    """a DS18B20's temperature in Celsius, or None if it gave none.

    Takes most of a second, while the probe measures.
    """
    path = os.path.join(folder, 'temperature')
    try:
        if os.path.isfile(path):
            with open(path) as fh:
                text = fh.read().strip()
            celsius = int(text) / 1000.0 if text else None
        else:
            celsius = fromSlave(os.path.join(folder, 'w1_slave'))
    except (OSError, ValueError):
        return None
    if celsius == POWER_ON:
        return None
    return celsius


def fromSlave(path):
    """a reading from w1_slave, the older file: a line ending YES when the
    check passed, then one ending t= and thousandths of a degree"""
    with open(path) as fh:
        lines = fh.read().splitlines()
    if len(lines) < 2 or not lines[0].strip().endswith('YES'):
        return None
    _, sep, value = lines[1].partition('t=')
    return int(value) / 1000.0 if sep else None


def overlay(theirs, ours):
    """another provider's conditions with these readings in place of
    theirs, or just the readings where there are none.

    ours holds temp, humidity and pressure, each one or None.  Their
    humidity was measured at their temperature, so with only our
    temperature it does not carry over.  Their dew point does - it is
    close to the same across a town - and humidity and feels-like are
    worked out again from it.
    """
    from PiClock3.Weather import Weather
    ours = {k: v for k, v in ours.items() if v is not None}
    c = dict(theirs or {})
    if not ours:
        return c or None
    if 'pressure' in ours:
        c['pressure'] = ours['pressure']
    if 'temp' not in ours and 'humidity' not in ours:
        return c

    dew = c.get('dew')
    if dew is None:
        dew = Weather.dewPoint(c.get('temp'), c.get('humidity'))
    c.update((k, ours[k]) for k in ('temp', 'humidity') if k in ours)
    temp = c.get('temp')
    if 'humidity' in ours:
        humidity = ours['humidity']
        dew = Weather.dewPoint(temp, humidity)
    elif dew is not None:
        humidity = Weather.humidity(temp, dew)
    else:
        humidity = None

    worked = {'dew': dew, 'humidity': humidity,
              'feels-like': Weather.feelsLikeFromHumidity(
                  temp, humidity, c.get('wind'))}
    for key, value in worked.items():
        if value is None:
            c.pop(key, None)
        else:
            c[key] = value
    return c


def line(template, labels, readings, show):
    """the template with each sensor's reading in place of its name.

    Empty, it is what PiClock v1 drew: each name and its reading.  A name
    in braces that is no sensor's is left for the clock to fill in, the
    way {location.latitude} is.  readings holds (quantity, value), and
    show turns one into the words drawn.
    """
    if not template:
        template = '   '.join('%s {%s}' % (label, label) for label in labels)

    def shown(match):
        label = match.group(1)
        if label not in labels:
            return match.group(0)
        quantity, value = readings.get(label, (None, None))
        return MISSING if value is None else show(quantity, value)

    return NAME.sub(shown, template)
