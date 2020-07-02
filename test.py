import serial
import time
import unittest

"""open another terminal and run this script serve as a virual COM and test"""

BAUD    = 115200
BYTE_S  = 8
PARITY  = serial.PARITY_NONE
STOPBIT = 2
PORT   = "COM2"
TERMINATOR = b'\0'

device = serial.Serial(PORT, BAUD, BYTE_S, PARITY, STOPBIT)
payload = [0x68, 0x77, 0x78]

device.write(b'\x68' + TERMINATOR)
device.flush()
time.sleep(0.5)
