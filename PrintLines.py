import queue
import serial.threaded
import traceback
import sys

#thread protocols
class PrintLines(serial.threaded.LineReader):
    def __init__(self):
        super(PrintLines, self).__init__()
        #thread safe queue to store reading inputs
        self.input_q = queue.Queue()

    def connection_made(self, transport):
        super(PrintLines, self).connection_made(transport)
        sys.stdout.write('port opened\n')

    def handle_line(self, data):
        sys.stdout.write('line received: {}\n'.format(repr(data)))
        self.input_q.put(data)
        print("handled", list(self.input_q.queue))

    def connection_lost(self, exc):
        if exc:
            traceback.print_exc(exc)
        sys.stdout.write('port closed\n')

    def is_ready(self):
        return not self.input_q.empty()

    def get_data(self):
        try:
            data = self.input_q.get(timeout = 0.5)
        except queue.Empty:
            data = None
        return data
