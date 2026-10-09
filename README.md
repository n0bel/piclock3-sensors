# piclock3-sensors

Sensors wired to a [PiClock3](https://github.com/n0bel/PiClock3)'s own Pi:
the temperature inside, or outside the window, or of the Pi itself.  It
shows them as a line of text, the way PiClock v1 did, and can put them in
the current-conditions panel in place of a weather service's.  It's
[issue #37](https://github.com/n0bel/PiClock3/issues/37) of PiClock3.

It has read the Pi's own temperature on a Pi 4.  It hasn't read a DS18B20
or an I2C sensor on real hardware yet.

## What it reads

The Linux kernel does the talking to each sensor and shows its readings as
small files, so this plugin needs nothing beyond Python, whatever the
chip.

- **DS18B20 thermometers** on the 1-Wire bus, and the others of that
  family: DS18S20, DS1822, DS1825 and DS28EA00.
- **I2C sensors with a kernel driver**, loaded by Raspberry Pi OS's
  `i2c-sensor` overlay.  That covers temperature, humidity and pressure
  from parts such as the BME280, BME680, BMP280, BMP380, SHT3x, SHT4x,
  AHT10, AHT20, HTU21, Si7020, TMP102, TMP117 and LM75.  The overlay's own
  README lists them all: `/boot/firmware/overlays/README`.
- **The Pi itself:** its processor's temperature is always there.

## Finding your sensors

```
cd ~/PiClock3
python3 plugins/Sensors/probes.py
```

prints each reading the kernel has, the way the config names it:

    w1-28-0000058e0f0c        22.5°C
    iio-bme280-temp           21.9°C
    iio-bme280-humidity       46%
    iio-bme280-pressure       1013.2 mb
    hwmon-cpu_thermal-temp1   36.0°C

With two of the same sensor, warm one in your hand and run it again.  A
running clock also lists, in its log, any reading its config doesn't name.

## Naming it in a config

It's a provider: it reads the sensors once, and widgets draw what it says.

**As a line of text,** drawn by the shipped Text widget:

```yaml
providers:
  sensors:
    plugin: plugins.Sensors
    probes:
      Inside:  w1-28-0000058e0f0c
      Outside: w1-28-0000031b54e7

widgets:
  indoors:
    plugin: PiClock3.Text
    region: bottom
    text-provider: sensors
```

That draws `Inside 22.5°C   Outside 3.0°C`.  `text:` writes the line
yourself, with each name in braces where its reading goes:

```yaml
    text: 'Inside {Inside}, outside {Outside}'
```

**In the current-conditions panel.**  A sensor on the Pi knows the
temperature, and maybe the humidity and pressure, but not the sky or the
wind.  So it hands on another provider's conditions - METAR, Open-Meteo,
or an MQTT plugin listening to your own station - with your readings in
place of theirs:

```yaml
providers:
  metar: {plugin: PiClock3.Metar, METAR: KMSP}
  sensors:
    plugin: plugins.Sensors
    probes:
      Inside:  w1-28-0000058e0f0c
      Outside: w1-28-0000031b54e7
    text: 'Inside {Inside}'
    conditions-provider: metar
    conditions:
      temp: Outside

widgets:
  current-conditions:
    plugin: PiClock3.CurrentConditions
    region: current
    conditions-provider: sensors
```

With only your temperature, the humidity and feels-like are worked out
again from the other provider's dew point, which is close to the same
across a town.  With your own humidity, the dew point comes from yours.

| setting | |
|---|---|
| `probes` | readings by the name the clock shows, each as `probes.py` prints it |
| `text` | the line, with a name in braces where its reading goes.  Empty shows each name and reading |
| `refresh` | seconds between readings, 60 |
| `conditions-provider` | the provider whose conditions are handed on |
| `conditions` | which reading stands in for `temp`, `humidity` and `pressure` |

Readings are shown in the clock's own units: set `units: metric` and the
line says °C and hPa.

`examples/sensors.yaml` is a clock with both.

## Wiring

**A DS18B20** has three legs.  Facing its flat side, legs down, they are
ground, data and power, left to right:

    DS18B20          Pi header
    left, ground     pin 9, ground
    middle, data     pin 7, GPIO4
    right, power     pin 1, 3.3V

A 4.7 kΩ resistor from data to 3.3V makes a long cable reliable.  More
probes go on the same three wires, each found by its own id.

**An I2C sensor** has four connections:

    sensor     Pi header
    VIN        pin 1, 3.3V
    GND        pin 9, ground
    SDA        pin 3, GPIO2
    SCL        pin 5, GPIO3

I2C needs GPIO2 and GPIO3.  PiClock v1 put its infrared receiver on GPIO3,
so a clock wired that way moves the receiver to another pin first -
[piclock3-controls](https://github.com/n0bel/piclock3-controls) uses
GPIO18.

## Installing

Needs PiClock3 2026.10.09 or later.  Then, on the Pi:

```
cd ~/PiClock3
git clone https://github.com/n0bel/piclock3-sensors plugins/Sensors
```

Then a line in `/boot/firmware/config.txt` (`/boot/config.txt` on
Bullseye) for each kind of sensor, and a reboot.

**For DS18B20s:**

```
dtoverlay=w1-gpio
```

GPIO4 unless you say otherwise: `dtoverlay=w1-gpio,gpiopin=17`.

**For an I2C sensor,** I2C turned on and the sensor's driver named:

```
dtparam=i2c_arm=on
dtoverlay=i2c-sensor,bme280
```

A sensor at its second address says so, and the overlay's README gives
each part's addresses:

```
dtoverlay=i2c-sensor,bme280,addr=0x77
```

Nothing needs root.

## Tests

```
python3 tests/devicestest.py
```

## License

MIT, the same as PiClock3.
