import serial
import serial.threaded
import threading
from PrintLines import PrintLines
from DebuggerInter import DebuggerInter
import time
import logging

LOG_NAME = "backlog.log"
logging.basicConfig(
    level = logging.DEBUG,
    format = "%(asctime)s %(levelname)s: %(message)s",
    datefmt = "%H:%M:%S",
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(LOG_NAME, mode = 'w')
    ]
)


PORT    = "COM3"
PORT_L  = "loop://"
BAUD    = 115200
PARITY  = serial.PARITY_NONE
STOPBIT = 2
PACKET_SIZE   = 8
RESPONSE_TIME = 10

loop = serial.serial_for_url(PORT_L, BAUD, PACKET_SIZE, PARITY, STOPBIT, timeout = 1)
#pc = serial.Serial(PORT, BAUD, BYTE_S, PARITY, STOPBIT, timeout = 1)


#a reader thread to poll data from serial port
reader_thread = serial.threaded.ReaderThread(loop, PrintLines)
debugger_inter = DebuggerInter(reader_thread, LOG_NAME)

#exit {with..as..} block will close the readerThread
with reader_thread as protocol:
    # a worker thread to update input data to TKINTER (midpoint connection between Tkiner and Pyserial)
    def worker(p, d):
        logging.info("worker thread running")
        #object with flag "do_run " to let outside kill the thread
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            if p.is_ready():
                d.timing_stop()
                d.update_rx_text(p.get_data())

            if d.TIMING and d.response_elapsed() > 10:
                logging.warning("No Response from FPGA")
                d.response_overtime_warning()
                d.timing_stop()

            time.sleep(0.1)
        logging.info("worker thread closed")
        return

    t = threading.Thread(target = worker, args=[protocol, debugger_inter])
    t.start()

    #start the UI loop
    debugger_inter.start()
    #kill worker thread
    t.do_run = False
    t.join()
