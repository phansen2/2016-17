from PyQt4 import QtCore
import socket
import struct
import joystickv1


class ConnectionManager:
    def __init__(self):
        self.ROVER_HOST = "192.168.0.40"
        self.ARM_HOST = "192.168.0.80"  # "192.168.7.2" # 7.2 for over USB
        self.SCIENCE_HOST = "192.168.0.90"
        self.LOCAL_HOST = "127.0.0.1"
        self.ROVER_TCP_PORT = 8841
        self.ROVER_PORT = 8840
        self.ARM_PORT = 53204
        self.SCIENCE_PORT = 5000

        self.auto = AutonomousConnection(self.ROVER_HOST, self.ROVER_TCP_PORT)
        # Kill the thread when the work is done
        self.auto.finished.connect(self.auto.quit)

        self.drive = DriveConnection(self.ROVER_HOST, self.ROVER_PORT)
        self.drive.start()

        self.arm = ArmConnection(self.ARM_HOST, self.ARM_PORT)
        self.arm.start()

        self.science = ScienceConnection(self.SCIENCE_HOST, self.SCIENCE_PORT)
        self.science.start()

    def enable_tcp(self, enable):
        if enable:
            self.auto.start()

    # Safely close all threads and sockets
    def shutdown(self):
        # Close the socket then kill the thread
        if self.auto.auto_sock is not None:
            self.auto.auto_sock.shutdown(socket.SHUT_RDWR)
            self.auto.auto_sock.close()
        self.auto.quit()

        if self.science.science_sock is not None:
            if self.science.connected:
                self.science.science_sock.shutdown(socket.SHUT_RDWR)
            self.science.science_sock.close()
        self.science.quit()

        # Kill the thread
        self.drive.quit()

        self.arm.quit()


# TODO conform to python's conventions for abstract classes instead of passing with a comment
class UdpConnection(QtCore.QThread):
    def __init__(self, host, port):
        QtCore.QThread.__init__(self)

        self.host = host
        self.port = port

        # UDP connection to the rover
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    # Subclasses implement this!!
    def send_message(self):
        pass

    def receive_message(self):
        pass

    def run(self):
        while True:
            self.send_message()
            self.receive_message()
            self.msleep(10)


class DriveConnection(UdpConnection):
    sensorUpdate = QtCore.pyqtSignal([dict])
    gpsUpdate = QtCore.pyqtSignal([tuple])

    def __init__(self, host, port):
        UdpConnection.__init__(self, host, port)

        # Indicates whether the rovers is in autonomous mode
        self.auto = False

        # Indicates whether emergency stop has been pressed (CANNOT BE UNDONE)
        # Reset the UI if emergency stopped
        self.stop = False

        self.joys = joystickv1.getJoysticks()
        self.joys.start()

        self.timer = None

    def enable_tcp(self, enable):
        self.auto = enable

    def stopping(self):
        self.stop = True

    def send_message(self):
        """
        Sends the rover throttle and steering information from joystick axises
        :return: None
        """

        throttle = 0
        steering = 0

        try:
            # Emit drive of zero if emergency stop isn't enabled
            if self.stop is not False:
                throttle = self.joys.joystick_axis[0][1]
                steering = self.joys.joystick_axis[0][0]
        except:
            pass
        else:
            throttle = translateValue(throttle, -32768, 32768, 255, -255)
            steering = translateValue(steering, -32768, 32768, -100, 100)
            if abs(throttle) < 20:
                throttle = 0
            if abs(steering) < 20:
                steering = 0

        # Put the first 2 boolean values in the buffer
        buff = struct.pack("<?hh", self.auto, int(throttle), int(steering))

        # Will send even if we can't reach the rover?
        self.sock.sendto(buff, (self.host, self.port))

    def receive_message(self):
        """
        Receive the incoming UDP packets, unpack them and emit them so other UI components can use them
        :return: Emit a dictionary of sensor values
        :return: Emit a tuple of lat lng coordinates
        """

        try:
            rover_data = self.sock.recv(1024)
        except socket.error:
            # Do nothing
            pass
        else:
            # Unpack the first six floats of the packet
            tup = struct.unpack_from("<ffffffff", rover_data, 0)
            pot = tup[0]
            mag = tup[1]
            enc_1 = tup[2]
            enc_2 = tup[3]
            enc_3 = tup[4]
            enc_4 = tup[5]
            lat = tup[6]
            lng = tup[7]

            dictionary = {"Potentiometer": str(pot), "Magnetometer": str(mag),
                          "Drive Encoder 1": str(enc_1), "Drive Encoder 2": str(enc_2), "Drive Encoder 3": str(enc_3),
                          "Drive Encoder 4": str(enc_4)}

            self.sensorUpdate.emit(dictionary)
            self.gpsUpdate.emit((lat, lng))


class ArmConnection(UdpConnection):
    def __init__(self, host, port):
        super(self.__class__, self).__init__(host, port)
        # Make this joystick # 2
        self.joys = joystickv1.getJoysticks()
        self.joys.start()

        self.JOYSTICK_NUM = 0

    def send_message(self):
        if not self.joys.ready:
            return
        # Don't run if joystick not plugged in
        if len(self.joys.joystick_axis) < self.JOYSTICK_NUM + 1:
            return

        # These mappings are for my Logitech F710 controller. 
        # Change accordingly if your controller is different
        base_rotation = self._joy_axis(2)  # Triggers
        shoulder = - self._joy_axis(1)  # Left stick Y axis
        elbow = self._joy_axis(3)  # Right stick Y axis
        wrist_lift = self._button_axis(1, 3)  # B is down, Y is up (B is right, Y is up)
        wrist_rotation = self._hat_axis(4, 5)  # Bumpers
        hand_grip = self._button_axis(2, 0)  # X- open hand, A- Close hand. (x left, a bottom)

        buff = struct.pack("<ffffff", base_rotation, shoulder, elbow, wrist_lift, wrist_rotation, hand_grip)

        # print (base_rotation, shoulder, elbow, wrist_lift, wrist_rotation, hand_grip)

        # Will send even if we can't reach the rover?
        self.sock.sendto(buff, (self.host, self.port))

    def _joy_axis(self, axisNum):
        """
        Returns the value at the specificed joystick axis. The value will be on
        the scale of 0-1.
        """
        val = self.joys.joystick_axis[self.JOYSTICK_NUM][axisNum];
        val /= 32768.0

        # Deadzone
        return 0 if (abs(val) < .10) else val

    def _button_axis(self, forwardBtn, reverseBtn):
        if self.joys.joystick_button[self.JOYSTICK_NUM][forwardDir]:
            return 1
        elif self.joys.joystick_button[self.JOYSTICK_NUM][reverseDir]:
            return -1
        else:
            return 0


class ScienceConnection(QtCore.QThread):
    sensorUpdate = QtCore.pyqtSignal([dict])

    def __init__(self, host, port):
        super(self.__class__, self).__init__()

        self.host = host
        self.port = port

        self.connected = False
        self.failed = 0

        self.science_sock = None

    def run(self):
        # Initial connection attempt
        self.connect(5)

        while True:
            if self.failed < 10 and self.connected:
                self.receive_message()
                self.msleep(10)
            else:
                # Disconnect the socket and try to reconnect
                self.connected = False
                self.failed = 0
                if self.science_sock is not None:
                    self.science_sock.shutdown(socket.SHUT_RDWR)
                    self.science_sock.close()
                self.connect(10)

    def connect(self, retry):
        try:
            self.science_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.science_sock.connect((self.host, self.port))
        except socket.error:
            print "Failed to Connect to Science Station retrying in 10 seconds"
            self.sleep(10)
            self.connect(retry - 1)
        else:
            self.connected = True

    def send_message(self):
        if self.connected:
            buff = struct.pack(">ic18sc", 0x00000000, 0x80, "I can haz picture?", 0x00)
            self.science_sock.send(buff)

    def receive_message(self):
        """
        Receive the incoming UDP packets, unpack them and emit them so other UI components can use them
        :return: Emit a dictionary of sensor values
        :return: Emit a tuple of lat lng coordinates
        """

        try:
            science_data = self.science_sock.recv(1024)
        except socket.error:
            self.failed = self.failed + 1
        else:
            # Unpack the first six floats of the packet
            tup = struct.unpack_from(">ic", science_data, 0)
            ide = tup[1]

            if ide == 0x00:
                tup = struct.unpack_from(">hihhh", science_data, 2)
                distance = tup[0]
                uv = tup[1]
                thermo_ext = tup[2]
                thermo_int = tup[3]
                humidity = tup[4]
                dictionary = {"Distance": str(distance), "UV": str(uv),
                              "Thermo Internal": str(thermo_ext), "Thermo External": str(thermo_int),
                              "Humidity": str(humidity)}
                self.sensorUpdate.emit(dictionary)
            elif ide == 0x02:
                tup = struct.unpack_from(">hhh?", science_data, 2)
                enc1 = tup[0]
                enc2 = tup[1]
                enc3 = tup[2]
                limit = tup[3]
                dictionary = {"Science Encoder 1": str(enc1), "Science Encoder 2": str(enc2),
                              "Science Encoder 3": str(enc3), "Limit Switch": str(limit)}
                self.sensorUpdate.emit(dictionary)


# Open a TCP connect in a separate thread
class AutonomousConnection(QtCore.QThread):
    requestMarkers = QtCore.pyqtSignal()
    tcp_enabled = QtCore.pyqtSignal(bool)

    def __init__(self, host, port):
        super(self.__class__, self).__init__()

        self.ROVER_HOST = host
        self.ROVER_TCP_PORT = port
        self.auto_sock = None
        self.markers = []

    def set_markers(self, markers):
        self.markers = markers

    def run(self):
        # Ask the map for markers
        self.requestMarkers.emit()

        # TCP connection to the rover
        try:
            self.auto_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.auto_sock.connect((self.ROVER_HOST, self.ROVER_TCP_PORT))
        except socket.error:
            print "Failed to Connect to Drive Over TCP"
            self.tcp_enabled.emit(False)
        else:
            self.tcp_enabled.emit(True)
            self.send_data()

    def send_data(self):
        for i in range(0, len(self.markers)):

            lat = float(self.markers[i][0])
            lng = float(self.markers[i][1])

            if i == len(self.markers) - 1:
                self.send_auto_mode(False, lat, lng)
            else:
                self.send_auto_mode(True, lat, lng)

        self.close_tcp()

    def send_auto_mode(self, more, lat, lng):

        # Put the first boolean value in the buffer
        buff = struct.pack("<?ff", more, lat, lng)
        self.auto_sock.send(buff)

    def close_tcp(self):
        if self.auto_sock is not None:
            self.auto_sock.shutdown(socket.SHUT_RDWR)
            self.auto_sock.close()
            self.auto_sock = None


# translate values from one range to another
def translateValue(value, inMin, inMax, outMin, outMax):
    """
    Linearly maps from one range to another range
    :param value: Input value to convert
    :param inMin: Bottom of the input range
    :param inMax: Top of the input range
    :param outMin: Bottom of the output range
    :param outMax: Top of the output range
    :return: Value scaled to the new range dimensions
    """
    # Figure out how 'wide' each range is
    inSpan = inMax - inMin
    outSpan = outMax - outMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - inMin) / float(inSpan)

    # Convert the 0-1 range into a value in the right range.
    return outMin + (valueScaled * outSpan)
