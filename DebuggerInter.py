import tkinter as tk
from tkinter import scrolledtext
import time
import logging
import os

DROP_DOWN_MENU = {
"DUMP MEMORY": b'\x00',
"LOAD ADDRESS": b'\x20',      #0x2-
"LOAD DATA": b'\x40',         #0x4-
"READ LOWER BYTE": b'\xE0'  #0xE-
}



class DebuggerInter():
    def __init__(self, serial_handle, log_name):
        self.serial_handle = serial_handle
        self.rx_byteCount = 0
        self.response_start_time = 0
        self.TIMING = False
        self.byte_buffer = []
        self.BYTES_COUNTER = 0

        #tkinter setup
        self.main_frame = tk.Tk()
        self.main_frame.title("UART Debugger Console")

        #top menu bar
        self.menubar = tk.Menu(self.main_frame)
        self.main_frame.config(menu = self.menubar)

        self.backlog_menu = tk.Menu(self.menubar, tearoff = 0)
        self.menubar.add_cascade(label = "Backlog", menu = self.backlog_menu)
        self.backlog_menu.add_command(label = "Open Backlog", command = lambda: os.startfile(log_name))

        self.help_menu = tk.Menu(self.menubar, tearoff = 0)
        self.menubar.add_cascade(label = "Help", menu = self.help_menu)
        self.help_menu.add_command(label = "NO HELP")




        #receive box
        self.rx_console = tk.LabelFrame(self.main_frame, text = "Receive Data", padx=5, pady=10)
        self.rx_console.grid(row = 0, column = 0, sticky = "NSEW")
        self.rx_text = scrolledtext.ScrolledText(self.rx_console, state = "disabled")
        self.rx_text.grid(row = 0, column = 0, sticky = "NSEW")
        self.rx_text.tag_config("warning", foreground = "red")

        #transimit box
        self.tx_console = tk.LabelFrame(self.main_frame, text = "Transmit Data", padx=5, pady=10)
        self.tx_console.grid(row = 1, column = 0, sticky = "NSEW")
        self.tx_text = scrolledtext.ScrolledText(self.tx_console)
        self.tx_text.grid(row = 0, column = 0, sticky = "NSEW")
        self.tx_text.tag_config('warning', foreground = 'red')

        #bottom widges block
        self.command_frame = tk.Frame(self.tx_console)
        self.command_frame.grid(row = 1, column = 0, pady = 5, sticky = "NSEW")

        #dropdown
        self.command_var = tk.StringVar(value = "Choose a Command")
        #dropdown callback
        def onChange_dropdown(*args):
            command = self.command_var.get()
            if (command == "DUMP MEMORY") or (command == "READ LOWER BYTE"):
                self.entry_box.configure(state = "disabled")
            else:
                self.entry_box.configure(state = "normal")
        self.command_var.trace("w", onChange_dropdown)

        self.drop_down = tk.OptionMenu(
                        self.command_frame,
                        self.command_var,
                        *DROP_DOWN_MENU.keys())
        self.drop_down.configure(bg = "light grey")
        self.drop_down.grid(row = 0, column = 0)

        #entry box
        self.entry_box_var = tk.StringVar()
        self.entry_box = tk.Entry(self.command_frame, textvariable = self.entry_box_var)
        self.entry_box.grid(row = 0, column = 1, ipadx = 60, padx = 15, sticky = "NSEW")

        self.tx_apply_button = tk.Button(self.command_frame, text = "APPLY",bg = "light grey", command = lambda: self.processApplyButton())
        self.tx_apply_button.grid(row = 0, column = 1, padx = 15, ipadx = 10, sticky = "E")

        self.tx_send_button = tk.Button(self.tx_console, text = "SEND", bg="light blue", command = lambda: self.processSendButton())
        self.tx_send_button.grid(row = 2, column = 0, pady = 15, ipadx = 50, ipady = 2)

        self.tx_apply_button.bind("<Enter>", lambda event: self.tx_apply_button.configure(bg = "white"))
        self.tx_apply_button.bind("<Leave>", lambda event: self.tx_apply_button.configure(bg = "light grey"))
        self.tx_send_button.bind("<Enter>", lambda event: self.tx_send_button.configure(bg = "white"))
        self.tx_send_button.bind("<Leave>", lambda event: self.tx_send_button.configure(bg = "light blue"))

        #resizing factor  (uesless for now)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure((0, 1), weight=1)

        self.rx_console.columnconfigure(0, weight=1)
        self.rx_console.rowconfigure(0, weight=1)

        self.tx_console.columnconfigure(0, weight=1)
        self.tx_console.rowconfigure(0, weight=1)

        self.command_frame.columnconfigure(0, weight=1)
        self.command_frame.columnconfigure(1, weight=5)
        self.command_frame.rowconfigure(0, weight=1)

    #"send" button onClick callback
    def processSendButton(self):
        #text processing
        text = self.tx_text.get("1.0", "end")
        command_list = text.split()

        #send commands
        for command in command_list:
            #parse input
            command = command.strip() #delete trailing newlines and whitespaces
            try:
                byteToSend = bytes.fromhex(command)
                self.send(byteToSend)
            except ValueError as e:
                #echo error to the Console
                self.tx_text.delete('1.0', "end")
                self.tx_text.insert('1.0', e, "warning")
                logging.warning("Transimtted Address/Data has format error")
        #prepare rx console for upcoming rx data
        self.clear()
        bytes_in_str = ' '.join(self.byte_buffer)
        if len(bytes_in_str):
            logging.info("Sent Data Packet Overview: {}".format(bytes_in_str))
            self.byte_buffer.clear()

    #"apply" button onClick callback
    def processApplyButton(self):
        command = self.command_var.get()
        if command == "Choose a Command" or command not in DROP_DOWN_MENU:
            return
        byte_template = DROP_DOWN_MENU[command]

        #prepare tx/rx console for upcoming rx data
        self.clear()
        self.tx_text.delete('1.0', "end")

        bytes_in_str = ''
        if (command == "DUMP MEMORY") or (command == "READ LOWER BYTE"):
            result_byte = byte_template
            self.send(result_byte)
        elif (command == "LOAD ADDRESS") or (command == "LOAD DATA"):
            address = self.entry_box_var.get()
            #parse the address
            if not len(address) == 8:
                self.tx_text.insert('1.0', "Please Check the Address/Data Format", "warning")
            else:
                for bit in address:
                    result_byte = bytes([int(bit, 16) | byte_template[0]]) #ORing operation
                    self.send(result_byte)
        bytes_in_str = ' '.join(self.byte_buffer)
        self.tx_text.insert('end', bytes_in_str)
        logging.info("Sent Data Packet Overview: {}".format(bytes_in_str))
        self.byte_buffer.clear()

    def start(self):
        self.main_frame.mainloop()

    def update_rx_text(self, data):
        #assuming one byte receiving at a time
        if data is not None:
            self.rx_text.configure(state = "normal")
            if self.rx_byteCount <= 0:
                self.rx_text.insert('end', data.hex())
            else:
                self.rx_text.insert('end', ' ' + data.hex())
            self.rx_text.configure(state = "disabled")
            self.rx_byteCount += 1

    def send(self, byteToSend):
        """send ONE byte at a time, in case when byteToSend is a sequence
           serial.write() will chop the sequence and send ONE byte at a time"""
        #record onset time of first byte sent to FPGA
        if not self.TIMING:
            self.response_start_time = time.perf_counter()
            self.timing_begin()
        result = self.serial_handle.serial.write(byteToSend)
        if result >= 1:
            logging.info("Successfully sent Byte: {}".format(byteToSend.hex()))
            self.byte_buffer.append(byteToSend.hex())
        else:
            logging.warning("Failed to sent Byte: {}".format(byteToSend.hex()))
        return result

    def clear(self):
        #prepare/clear rx console
        self.rx_text.configure(state = "normal")
        self.rx_text.delete('1.0', "end")
        self.rx_text.configure(state = "disabled")
        self.rx_byteCount = 0

    def timing_begin(self):
        self.TIMING = True

    def timing_stop(self):
        self.TIMING = False

    def response_elapsed(self):
        return time.perf_counter() - self.response_start_time

    def response_overtime_warning(self):
        self.rx_text.configure(state = "normal")
        self.rx_text.insert('end', "No Response from FPGA", "warning")
        self.rx_text.configure(state = "disabled")
