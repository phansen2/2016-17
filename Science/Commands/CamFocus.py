import sys
import Parse
import Error
import Util
from Packet import AuxCtrlID
from Command import Command
from Motor import Servo

DEFAULT_PIN = "P8_45"


class CamFocus(Command):

    def __init__(self, servo_pin=DEFAULT_PIN):
        self._motor = Servo(servo_pin)
        Command.__init__(self)

    def initialize(self):
        if not self._motor.isStarted():
            self._motor.__init__(self._motor._pin)

    def run(self, setpoint):
        set = self.setpoint()
        self._motor.moveTo(self.setpoint())

    def setpoint(self, setpoint=None):
        self._setpoint = Parse.aux_ctrl[AuxCtrlID.CamFocusPos + 1]
        return self._setpoint

    def stopSafe(self):
        self._motor.stop()

    def isFinished(self):
        return False  # Tells when to finish command
