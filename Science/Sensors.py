import sys
import time
import UV_Sensor as UV
import Thermocouple
import DistanceSensor
import Limit
import PID
import Humidity
import Adafruit_BBIO.ADC as ADC  # Ignore compilation errors
import Encoder
import Util
from threading import Thread
import CommHandler as Comms

# Define constants
PinDataIn = "P9_18"
PinChipSel = "P9_17"
PinClock = "P9_22"
UV_ADDR_LSB = 0x38
DIST_ADDR = 0x52

# Communication Setup
MAIN_IP = '192.168.0.60'
PRIMARY_UDP_SEND_PORT = 8840
INTERNAL_IP = '127.0.0.1'
INTERNAL_UDP_RECEIVE_PORT = 5000

# Initialize hardware
ADC.setup()
CommHandling = Comms.CommHandler(INTERNAL_IP, INTERNAL_UDP_RECEIVE_PORT)

# Start Communication Thread
COMMS_THREAD = Thread(target=CommHandling.receiveMessagesOnThread)
COMMS_THREAD.start()

# Create Sensors
UV_Sens = UV.UV(UV_ADDR_LSB)
Therm = Thermocouple.Thermocouple(PinClock, PinChipSel, PinDataIn)
Dist = DistanceSensor.DistanceSensor()
humidity = Humidity.Humidity(1)
# Need to write in the actual pin values here.
encoder1 = Encoder.Encoder("PINA", "PINB", 220)
encoder2 = Encoder.Encoder("PINA", "PINB", 220)
encoder3 = Encoder.Encoder("PINA", "PINB", 220)


# Setup Sensors
UV_Sens.setup(2)
Dist.startRanging()

while True:

    # Read Sensor Data
    time.sleep(0.01)
    temp = Therm.getTemp()
    time.sleep(0.01)
    internal = Therm.getInternalTemp()
    uvData = UV_Sens.getData()
    humidityData = humidity.read()
    distance = Dist.getDistance()

    # Write data to test
    sys.stdout.write('{0}\n'.format(distance))
    #sys.stdout.write('{0}, '.format(pidCtrl.getOutput()))
    #sys.stdout.write('{0:{fill}16b} ({0}),'.format(uvData, fill='0'))
    #sys.stdout.write(time.strftime("%Y-%m-%d %H:%M:%S,"))
    #sys.stdout.write('{0:0.2F};'.format(temp))
    sys.stdout.flush()


    #print('    Internal Temperature: {0:0.3F}*C'.format(internal))

    time.sleep(0.25)
