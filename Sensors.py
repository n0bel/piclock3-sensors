"""Sensors wired to the Pi, as a line of text and as conditions.

As a text source, the shipped Text widget draws what it says, each reading
in the clock's own units.  As a weather source, it hands on another
provider's conditions with its own temperature, humidity and pressure in
place of theirs: a sensor on the Pi knows those, and not the sky or the
wind.
"""
import logging
import threading
import time

from PyQt5.QtCore import QTimer, pyqtSignal

from PiClock3.TextSource import TextSource
from PiClock3.Weather import Weather

from . import devices

logger = logging.getLogger(__name__)


class Sensors(TextSource, Weather):

    # reading a DS18B20 takes most of a second, so readings happen on a
    # thread of their own, and this carries them back to Qt's
    readings = pyqtSignal(dict)

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.subscribers = []
        self.current = {}
        self.wrapped = None
        self.readings.connect(self.arrived)

    def start(self):
        found = devices.probes()
        for key in sorted(set(found) - set(self.config['probes'].values())):
            logger.info('%s: %s, %s, is not under probes:', self.name, key,
                        found[key].quantity)
        thread = threading.Thread(target=self.poll, daemon=True)
        thread.start()
        # once the clock is running, because providers load in the order a
        # config lists them and the one wrapped may come after this one
        QTimer.singleShot(0, self.wrap)

    def wrap(self):
        name = self.config['conditions-provider']
        if not name:
            return
        self.wrapped = self.piclock.plugins.get(name)
        if self.wrapped is None:
            logger.error('%s: no provider %s', self.name, name)
            return
        self.wrapped.subscribe(self.changed)

    @property
    def attribution(self):
        """the wrapped provider's credit, since the sky is theirs"""
        return getattr(self.wrapped, 'attribution', '')

    def poll(self):
        """on its own thread, for as long as the clock runs"""
        warned = set()
        while True:
            found = devices.probes()
            got = {}
            for label, key in self.config['probes'].items():
                sensor = found.get(key)
                if sensor is None:
                    if key not in warned:
                        warned.add(key)
                        logger.error('%s: no sensor %s', self.name, key)
                    continue
                got[label] = (sensor.quantity, sensor.read())
            self.readings.emit(got)
            time.sleep(self.config['refresh'])

    def arrived(self, got):
        self.current = got
        self.changed()

    def changed(self):
        for fn in self.subscribers:
            fn()

    def subscribe(self, fn):
        self.subscribers.append(fn)

    def text(self):
        line = devices.line(self.config['text'], list(self.config['probes']),
                            self.current, self.show)
        return self.expand(line)

    def show(self, quantity, value):
        """a reading in the clock's own units.

        The set is named, because format() with none uses the set called
        default rather than the one the config chose.
        """
        units = self.piclock.units
        if quantity == 'temperature':
            return units.format('temperature', 'C', value,
                                setName=units.setName())
        if quantity == 'pressure':
            return units.format('altimeter', 'mb', value,
                                setName=units.setName())
        return '%.0f%%' % value

    def conditions(self):
        theirs = self.wrapped.conditions() if self.wrapped else None
        ours = {}
        for field, label in self.config['conditions'].items():
            _, value = self.current.get(label, (None, None))
            ours[field] = value
        return devices.overlay(theirs, ours)
