import tkinter as tk
from tkinter import scrolledtext
import time


class DebuggerInter():
    def __init__(self, serial_handle):
        self.serial_handle = serial_handle
        self.rx_byteCount = 0

        #tkinter setup
        self.main_frame = tk.Tk()
        self.main_frame.title("UART Debugger Console")

        #receive box
        self.rx_console = tk.LabelFrame(self.main_frame, text = "Receive Data", padx=5, pady=10)
        self.rx_console.grid(row = 1, column = 1)

        self.rx_text = scrolledtext.ScrolledText(self.rx_console, state = "disabled")
        self.rx_text.grid(row = 1, column = 1)

        #transimit box
        self.tx_console = tk.LabelFrame(self.main_frame, text = "Transmit Data", padx=5, pady=10)
        self.tx_console.grid(row = 2, column = 1)

        self.tx_text = scrolledtext.ScrolledText(self.tx_console)
        self.tx_text.grid(row = 1, column = 1)

        #"send" button onClick callback
        def processButton():
            #text processing
            text = self.tx_text.get("1.0", "end")
            command_list = text.split()

            #send commands
            for command in command_list:
                #parse input
                command = command.strip() #delete trailing newlines and whitespaces
                try:
                    byteToSend = bytes.fromhex(command)
                    print(byteToSend)
                    print("#Bytes sent: ", self.serial_handle.serial.write(byteToSend))
                except ValueError as e:
                    #echo error to the Console
                    self.tx_text.delete('1.0', "end")
                    self.tx_text.insert('1.0', e)
            #prepare/clear rx console
            self.rx_text.configure(state = "normal")
            self.rx_text.delete('1.0', "end")
            self.rx_text.configure(state = "disabled")
            self.rx_byteCount = 0

        self.tx_send_button = tk.Button(self.tx_console, text = "SEND", command = lambda: processButton() )
        self.tx_send_button.grid(row = 2, column = 1, sticky = "SE", padx=5, pady=8)

        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(3, weight=1)

        self.rx_console.columnconfigure(1, weight=1)
        self.rx_console.rowconfigure(1, weight=1)

        self.tx_console.columnconfigure(1, weight=1)
        self.tx_console.rowconfigure(2, weight=1)


    def start(self):
        self.main_frame.mainloop()

    def update_rx_text(self, data):
        #assuming one byte comming at a time
        print(tk.END)
        if data is not None:
            self.rx_text.configure(state = "normal")
            if self.rx_byteCount <= 0:
                self.rx_text.insert('end', data.hex())
            else:
                self.rx_text.insert('end', ' ' + data.hex())
            self.rx_text.configure(state = "disabled")
            self.rx_byteCount += 1
