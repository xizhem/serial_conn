import serial
import serial.threaded
import threading
from PrintLines import PrintLines
from DebuggerInter import DebuggerInter
import time

PORT    = "COM3"
PORT_L  = "loop://"
BAUD    = 115200
BYTE_S  = 8
PARITY  = serial.PARITY_NONE
STOPBIT = 2

loop = serial.serial_for_url(PORT_L, BAUD, BYTE_S, PARITY, STOPBIT, timeout = 1)
#pc = serial.Serial(PORT, BAUD, BYTE_S, PARITY, STOPBIT, timeout = 1)


#a reader thread to poll data from serial port
reader_thread = serial.threaded.ReaderThread(loop, PrintLines)
debugger_inter = DebuggerInter(reader_thread)

#exit {with..as..} block will close the readerThread
with reader_thread as protocol:
    # a worker thread to update input data to TKINTER
    def worker(p, d):
        print("worker thread running")
        #object with flag "do_run " to let outside kill the thread
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            if(p.is_ready() is True):
                d.update_rx_text(p.get_data())
            time.sleep(0.1)
        print("worker thread closed")
        return

    t = threading.Thread(target = worker, args=[protocol, debugger_inter])
    t.start()

    #start the UI loop
    debugger_inter.start()
    t.do_run = False
    t.join()


"""
except Exception as e:
    pc.close()
    raise e
"""
#clean up
