from PIL import Image
import socket
import sys
import math
import time
import RPi.GPIO as GPIO
from subprocess import call
from binascii import unhexlify
import signal
import traceback

Debug = False

# Cuts out the specified part of the image to prepare for sharpness calculations.
def PrepareImageData(ImgData, StartX, StartY, EndX, EndY):
    Output = [[0 for Y in range(StartY, EndY + 1)] for X in range(StartX, EndX + 1)];
    for Y in range(StartY, EndY):
        for X in range(StartX, EndX):
            Output[X - StartX][Y - StartY] = ImgData[X, Y]
    return Output;

# Calculates the sharpness of a prepared data set.
def GetSharpnessBasic(ImgData, Width, Height):
    Sum = 0;
    for Y in range(0, Height - 1):
        for X in range(0, Width - 1):
            Sum += ((ImgData[X+1][Y][0] - ImgData[X][Y][0]) ** 2);
            Sum += ((ImgData[X+1][Y][1] - ImgData[X][Y][1]) ** 2);
            Sum += ((ImgData[X+1][Y][2] - ImgData[X][Y][2]) ** 2);
            Sum += ((ImgData[X][Y][0] - ImgData[X][Y+1][0]) ** 2);
            Sum += ((ImgData[X][Y][1] - ImgData[X][Y+1][1]) ** 2);
            Sum += ((ImgData[X][Y][2] - ImgData[X][Y+1][2]) ** 2);
    return Sum;

def TestImage(File):
    if Debug:
            sys.stdout.write("=== Image: " + File + " ===\n");
    # Opens the image and gets basic parameters.
    ImgObj = Image.open(File);
    ImgDataRaw = ImgObj.load();
    SizeRaw = ImgObj.size;
    if Debug:
        sys.stdout.write("Raw dimensions: [W:" + str(SizeRaw[0]) + " H:" + str(SizeRaw[1]) + "]\n");

    # The region that will be checked for sharpness.
    Left = (SizeRaw[0] * 1/3);
    Right = (SizeRaw[0] * 2/3);
    Top = (SizeRaw[1] * 1/3);
    Bottom = (SizeRaw[1] * 2/3);
    Size = (Right - Left), (Bottom - Top);

    # Shrinks the data to the relevant region, and translates RGB into a single value for easier calculation.
    if Debug:
        sys.stdout.write("Shrinking to [W:" + str(Size[0]) + " H:" + str(Size[1]) + "] by using [X:" + str(Left) + "->" + str(Right) + "],[Y:" + str(Top) + "->" + str(Bottom) + "]\n");
    ImgData = PrepareImageData(ImgDataRaw, Left, Top, Right, Bottom);
    SharpnessBas = GetSharpnessBasic(ImgData, Size[0], Size[1]);
    if Debug:
        sys.stdout.write("Calculated sharpness: " + str(SharpnessBas) + "\n");
    return SharpnessBas;

# Calculates sharpness for a list of images.
def TestImageSet(Min, Max):
    Images = [];
    for I in range(Min, Max + 1):
        Images += ["test0" + str(I) + ".jpg"];

    for File in Images:
        sys.stdout.write(str(TestImage(File)));

# Taken from Util.py by @baldstrom.
def long_to_bytes(val, endianness='big'):
    if val < 0:
        return struct.pack('<l', val)
    if val == 0:
        return '\x00'
    width = val.bit_length()
    width += 8 - ((width % 8) or 8)
    fmt = '%%0%dx' % (width // 4)
    s = unhexlify(fmt % val)
    if endianness == 'little':
        s = s[::-1]
    return s

# Taken from Util.py by @baldstrom.
def long_to_byte_length(val, byte_length, endianness='big'):
    valBA = bytearray(long_to_bytes(val))
    if len(valBA) > byte_length:
        valBA = valBA[:byte_length]
    elif len(valBA) < byte_length:
        valBA = b'\x00'*(byte_length-len(valBA)) + valBA
    return valBA

def UserExit(signal, frame):
    sys.stdout.write("Ctrl+C detected, exiting...\n");
    GPIO.cleanup();
    sys.exit(0);

# Simply takes a picture.
def TakePicture():
    call(["fswebcam", "-r", "1600x1200", "test060.jpg"]);

# Sends a "move servo" packet to the BeagleBone. Used for AF.
def SendServo(NewValue):
    Timestamp = long_to_byte_length(int(time.time()), 4);
    ID = long_to_byte_length(0x81, 1);
    Command = long_to_byte_length(0x02, 1);
    Value = long_to_byte_length(NewValue, 4);
    try:
        Sock = socket.socket();
        Sock.connect(("192.168.0.90", 5000));
        Sock.send(Timestamp + ID + Command + Value);
        Sock.close()
    except:
        sys.stdout.write("Something went wrong when sending packet.\n");
        sys.stdout.write(traceback.format_exc());

# Executes the AF routine.
def DoAutofocus():
    TakePicture();
    sys.stdout.write("Picture taken, calculating sharpness...\n");
    Sharpness = TestImage("test060.jpg");
    sys.stdout.write("Sharpness: " + str(Sharpness) + "\n");
    SendServo(Sharpness % 360);
    sys.stdout.write("Packet sent.\n");

signal.signal(signal.SIGINT, UserExit)

GPIO.setmode(GPIO.BOARD);
InputPin = 16;
GPIO.setup(InputPin, GPIO.IN);
TakePic = False;
DoAF = False;

def CamTrigger(channel):
    global DoAF;
    global TakePic;
    time.sleep(0.150);
    if(GPIO.input(InputPin)):
        DoAF = False;
        TakePic = True;
    else:
        DoAF = True;
        TakePic = True;

PicFoci = [];

def Cycle(CurrFocus):
    PicFoci += [CurrFocus];
    Avg = AvgList(PicFoci);

def AvgList(List):
    Sum = 0;
    for I in List:
        Sum += I;
    return (Sum) / len(List);


GPIO.add_event_detect(InputPin, GPIO.RISING, callback=CamTrigger);
while True:
    if TakePic:
        if DoAF:
            DoAutofocus();
            TakePic = False;
        else:
            TakePicture();
            TakePic = False;
    time.sleep(0.050);
GPIO.cleanup();