"""Implements a servo in MPF."""
from mpf.core.delays import DelayManager

from mpf.core.device_monitor import DeviceMonitor
from mpf.core.events import event_handler
from mpf.core.platform import ServoPlatform
from mpf.core.system_wide_device import SystemWideDevice


@DeviceMonitor(_position="position")
class Servo(SystemWideDevice):

    """Represents a servo in a pinball machine.

    Args: Same as the Device parent class.
    """

    config_section = 'servos'
    collection = 'servos'
    class_label = 'servo'

    def __init__(self, machine, name):
        """Initialise servo."""
        self.hw_servo = None
        self.platform = None        # type: ServoPlatform
        self._position = None
        self.speed_limit = None
        self.acceleration_limit = None
        self._ball_search_started = False
        self.delay = DelayManager(machine.delayRegistry)
        super().__init__(machine, name)

    def _initialize(self):
        self.platform = self.machine.get_platform_sections('servo_controllers', self.config['platform'])

        for position in self.config['positions']:
            self.machine.events.add_handler(self.config['positions'][position],
                                            self._position_event,
                                            position=position)

        self.hw_servo = self.platform.configure_servo(self.config['number'])
        self._position = self.config['reset_position']
        self.speed_limit = self.config['speed_limit']
        self.acceleration_limit = self.config['acceleration_limit']

        if self.config['include_in_ball_search']:
            self.machine.events.add_handler("ball_search_started",
                                            self._ball_search_start)
            self.machine.events.add_handler("ball_search_stopped",
                                            self._ball_search_stop)

        self.set_speed_limit(self.speed_limit)
        self.set_acceleration_limit(self.acceleration_limit)

    @event_handler(1)
    def reset(self, **kwargs):
        """Go to reset position."""
        del kwargs
        self.go_to_position(self.config['reset_position'])

    @event_handler(5)
    def _position_event(self, position, **kwargs):
        del kwargs
        self.go_to_position(position)

    def go_to_position(self, position):
        """Move servo to position."""
        self._position = position
        if self._ball_search_started:
            return
        self._go_to_position(position)

    def _go_to_position(self, position):
        # linearly interpolate between servo limits
        position = self.config['servo_min'] + position * (
            self.config['servo_max'] - self.config['servo_min'])

        # call platform with calculated position
        self.hw_servo.go_to_position(position)

    def set_speed_limit(self, speed_limit):
        """Set speed parameter."""
        self.hw_servo.set_speed_limit(speed_limit)

    def set_acceleration_limit(self, acceleration_limit):
        """Set acceleration parameter."""
        self.hw_servo.set_acceleration_limit(acceleration_limit)

    def _ball_search_start(self, **kwargs):
        del kwargs
        # we do not touch self._position during ball search so we can reset to
        # it later
        self._ball_search_started = True
        self._ball_search_go_to_min()

    def _ball_search_go_to_min(self):
        self._go_to_position(self.config['ball_search_min'])
        self.delay.add(name="ball_search", callback=self._ball_search_go_to_max, ms=self.config['ball_search_wait'])

    def _ball_search_go_to_max(self):
        self._go_to_position(self.config['ball_search_max'])
        self.delay.add(name="ball_search", callback=self._ball_search_go_to_min, ms=self.config['ball_search_wait'])

    def _ball_search_stop(self, **kwargs):
        del kwargs
        # stop delay
        self.delay.remove("ball_search")
        self._ball_search_started = False

        # move to last position set
        self._go_to_position(self._position)
