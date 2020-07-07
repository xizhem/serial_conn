import serial
import serial.threaded
import threading
from PrintLines import PrintLines
from DebuggerInter import DebuggerInter
import time
import logging
import unittest

""" The unit tests will open one TK interface window for each test and require user
    manually supervising the test. To proceed to next test, simply close the current
    TK window and the script will automatically open a new one. This is due to the
    infinite loop running by TKinter and lack of testing module build into library.
    The test result will be printed to the console when all the windows/tests are
    opened/closed.  ---Xizhe
"""


LOG_NAME = "debug.log"
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

class TestLoopPort(unittest.TestCase):
    def setUp(self):
        self.loop = serial.serial_for_url(PORT_L, BAUD, PACKET_SIZE, PARITY, STOPBIT, timeout = 1)
        self.reader_thread = serial.threaded.ReaderThread(self.loop, PrintLines)
        self.debugger_inter = DebuggerInter(self.reader_thread, LOG_NAME)
        self.reader_thread.start()
        self.reader_thread._connection_made.wait()

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

                time.sleep(0.05)
            logging.info("worker thread closed")
            return

        self.t = threading.Thread(target = worker, args=[self.reader_thread.protocol, self.debugger_inter])
        self.t.start()


    def test_load_address(self):
        test_address_command = {
            "11111111" : "21 21 21 21 21 21 21 21",
            "1234abcd" : "21 22 23 24 2a 2b 2c 2d",
            "00000008" : "20 20 20 20 20 20 20 28",
            "0000000c" : "20 20 20 20 20 20 20 2c",
            "abcdabcd" : "2a 2b 2c 2d 2a 2b 2c 2d"
        }
        #debugging thread
        def load_address_worker():
            #wait for tkinter to boot
            time.sleep(0.5)
            self.helper(test_address_command, "LOAD ADDRESS")

        self.load_address_thread = threading.Thread(target = load_address_worker)
        self.load_address_thread.start()

        #start the UI loop
        self.debugger_inter.start()


    def test_load_data(self):
        test_load_command = {
            "ffffffff" : "4f 4f 4f 4f 4f 4f 4f 4f",
            "eeeeeeee" : "4e 4e 4e 4e 4e 4e 4e 4e",
            "dddddddd" : "4d 4d 4d 4d 4d 4d 4d 4d",
            "11111111" : "41 41 41 41 41 41 41 41",
            "1234abcd" : "41 42 43 44 4a 4b 4c 4d",
            "00000008" : "40 40 40 40 40 40 40 48",
        }

        #debugging thread
        def load_data_worker():
            #wait for tkinter to boot
            time.sleep(0.5)
            self.helper(test_load_command, "LOAD DATA")

        self.load_data_thread = threading.Thread(target = load_data_worker)
        self.load_data_thread.start()

        #start the UI loop
        self.debugger_inter.start()

    def test_dump_memory(self):
        test_dump_command = "00"

        def dump_memory_worker():
            #wait for tkinter to boot
            time.sleep(0.5)
            self.set_command("DUMP MEMORY")
            self.debugger_inter.processApplyButton()
            time.sleep(0.1)
            self.assertEqual(self.debugger_inter.rx_text.get("1.0", "end").strip(), test_dump_command)

        self.dump_thread = threading.Thread(target = dump_memory_worker)
        self.dump_thread.start()

        #start the UI loop
        self.debugger_inter.start()

    def test_read_byte(self):
        test_read_command = "e0"

        def read_byte_worker():
            #wait for tkinter to boot
            time.sleep(0.5)
            self.set_command("READ LOWER BYTE")
            self.debugger_inter.processApplyButton()
            time.sleep(0.1)
            self.assertEqual(self.debugger_inter.rx_text.get("1.0", "end").strip(), test_read_command)

        self.dump_thread = threading.Thread(target = read_byte_worker)
        self.dump_thread.start()

        #start the UI loop
        self.debugger_inter.start()

    def tearDown(self):
        #kill worker thread
        self.t.do_run = False
        self.t.join()
        self.reader_thread.close()

    def set_command(self, command):
        self.debugger_inter.command_var.set(command)

    def helper(self, test_dict, command):
        self.set_command(command)
        for k,v in test_dict.items():
            self.debugger_inter.entry_box_var.set(k)
            self.debugger_inter.processApplyButton()
            time.sleep(0.5)
            self.assertEqual(self.debugger_inter.rx_text.get("1.0", "end").strip(), v)


class TestCOMPort(unittest.TestCase):
    def setUp(self):
        self.pc = serial.Serial(PORT, BAUD, PACKET_SIZE, PARITY, STOPBIT, timeout = 1)
        self.reader_thread = serial.threaded.ReaderThread(self.pc, PrintLines)
        self.debugger_inter = DebuggerInter(self.reader_thread, LOG_NAME)
        self.reader_thread.start()
        self.reader_thread._connection_made.wait()

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

                time.sleep(0.05)
            logging.info("worker thread closed")
            return

        self.t = threading.Thread(target = worker, args=[self.reader_thread.protocol, self.debugger_inter])
        self.t.start()

    def test_FPGA_hang(self):
        """receive console should have red warning 'No Response from FPGA'
            after 10 sec casued by sending packet to disconnected port COM3
            """
        def hang_worker():
            #wait for tkinter to boot
            time.sleep(0.5)
            self.debugger_inter.tx_text.insert("1.0", "ab")
            self.debugger_inter.processSendButton()

        self.hang_worker = threading.Thread(target = hang_worker)
        self.hang_worker.start()

        #start the UI loop
        self.debugger_inter.start()


    def tearDown(self):
        #kill worker thread
        self.t.do_run = False
        self.t.join()
        self.reader_thread.close()

if __name__ == '__main__':
    unittest.main()
