try:
    from PiClock3 import __version__
except ImportError:
    # a PiClock3 from before it had a version
    __version__ = '0'

# the oldest PiClock3 this plugin runs on, the first with a version.  A
# SystemExit with a sentence is shown as that sentence, where any other
# error is a traceback.
if __version__ < '2026.10.09':
    raise SystemExit('Sensors needs PiClock3 2026.10.09 or later - '
                     'git pull in the PiClock3 folder')

from .Sensors import *  # noqa: E402,F401,F403
