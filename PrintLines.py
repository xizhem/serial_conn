import queue
import serial.threaded
import traceback
import sys
import logging

#thread protocols
class PrintLines(serial.threaded.LineReader):
    def __init__(self):
        super(PrintLines, self).__init__()
        #thread safe queue to store reading inputs
        self.input_q = queue.Queue()

    def connection_made(self, transport):
        super(PrintLines, self).connection_made(transport)
        logging.info('port opened\n')

    def handle_line(self, data):
        logging.info('Line received: {}'.format(data.hex()))
        self.input_q.put(data)

    def connection_lost(self, exc):
        if exc:
            traceback.print_exc()
        logging.info('port closed\n')

    def is_ready(self):
        return not self.input_q.empty()

    def get_data(self):
        try:
            data = self.input_q.get(timeout = 0.5)
        except queue.Empty:
            data = None
        return data
