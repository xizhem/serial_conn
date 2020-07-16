import tkinter as tk
from tkinter import scrolledtext
import serial.tools.list_ports
import time
import logging
import os

DROP_DOWN_MENU = {
"DUMP MEMORY": b'\x00',
"LOAD ADDRESS": b'\x20',      #0x2-
"LOAD DATA": b'\x40',         #0x4-
"READ BYTE": b'\xE0',    #0xE-
"READ DATA RANGE" : b'\x20'   #FF is just the same as loading, this command composite Load Address and READ BYTE

}

class DebuggerInter():
    def __init__(self, serial_handle, log_name):
        self.serial_handle = serial_handle      # Object <ReaderThread>
        self.rx_byteCount = 0
        self.response_start_time = 0
        self.TIMING = False
        self.byte_buffer = []
        self.BYTES_COUNTER = 0
        self.RANGE_MODE = False
        self.raw_data = ''

        #tkinter setup
        self.main_frame = tk.Tk()
        self.main_frame.title("UART Debugger Console")

        #top menu bar
        self.menubar = tk.Menu(self.main_frame)
        self.main_frame.config(menu = self.menubar)

        self.config_menu = tk.Menu(self.menubar, tearoff = 0)
        self.menubar.add_cascade(label = "Config", menu = self.config_menu)
        self.config_menu.add_command(label = "Change Serial Port", command = lambda: self.config_port())

        self.backlog_menu = tk.Menu(self.menubar, tearoff = 0)
        self.menubar.add_cascade(label = "Backlog", menu = self.backlog_menu)
        self.backlog_menu.add_command(label = "Open Backlog", command = lambda: os.startfile(log_name))

        self.edit_menu = tk.Menu(self.menubar, tearoff = 0)
        self.menubar.add_cascade(label = "Edit", menu = self.edit_menu)
        self.edit_menu.add_command(label = "Format as Hexdump", command = lambda: self.to_hexdump(False))
        self.edit_menu.add_command(label = "Format as Canonical Hexdump", command = lambda: self.to_hexdump(True))
        self.disable_edit_menu()

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
            if (command == "READ DATA RANGE" and not self.RANGE_MODE):
                self.add_range_command_widgets()
                self.enable_edit_menu()
            else:
                if self.RANGE_MODE:
                    self.remove_range_command_widgets()
                    self.disable_edit_menu()

            if (command == "DUMP MEMORY") or (command == "READ BYTE"):
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

        #resizing factor
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure((0, 1), weight=1)

        self.rx_console.columnconfigure(0, weight=1)
        self.rx_console.rowconfigure(0, weight=1)

        self.tx_console.columnconfigure(0, weight=1)
        self.tx_console.rowconfigure(0, weight=1)

        self.command_frame.columnconfigure(1, weight=5)
        self.command_frame.rowconfigure(0, weight=1)

    #"send" button onClick callback
    def processSendButton(self):
        #text processing
        raw_text = self.tx_text.get("1.0", "end")
        text = raw_text.split()

        #send commands
        for byte_str in text:
            #parse input
            byte_str = byte.strip() #delete trailing newlines and whitespaces
            try:
                byteToSend = bytes.fromhex(byte_str)
                self.send(byteToSend)
            except ValueError as e:
                #echo error to the Console
                self.tx_text.delete('1.0', "end")
                self.tx_text.insert('1.0', e, "warning")
                logging.warning("Transimtted Address/Data has format error")
        #prepare rx console for upcoming rx data
        self.clear_rx_console()
        bytes_in_str = ' '.join(self.byte_buffer)
        if len(bytes_in_str):
            logging.info("Sent Data Packet Overview: {}".format(bytes_in_str))
            self.byte_buffer.clear()

    #"apply" button onClick callback
    def processApplyButton(self):
        command = self.command_var.get()
        if command == "Choose a Command" or command not in DROP_DOWN_MENU:
            return
        byte_mask = DROP_DOWN_MENU[command]

        #prepare tx/rx console for upcoming rx data(do not clear in read data range command)
        self.clear_rx_console()
        self.tx_text.delete('1.0', "end")

        bytes_in_str = ''
        if (command == "DUMP MEMORY") or (command == "READ BYTE"):
            result_byte = byte_mask
            self.send(result_byte)

        elif (command == "LOAD ADDRESS") or (command == "LOAD DATA"):
            input_byte_str = self.entry_box_var.get()
            #parse the address/data
            if not len(input_byte_str) == 8:
                self.tx_text.insert('1.0', "Please Check the Address/Data Format", "warning")
            else:
                for lower_bits in input_byte_str:
                    result_byte = bytes([int(lower_bits, 16) | byte_mask[0]]) #ORing operation
                    self.send(result_byte)

        elif (command == "READ DATA RANGE"):
            from_address_str = self.range_var_1.get()
            to_address_str = self.range_var_2.get()
            self.raw_data = ''

            if not len(from_address_str) == 8:
                self.tx_text.insert('1.0', "Please Check the FIRST Address Format", "warning")
                return
            elif not len(to_address_str) == 8:
                self.tx_text.insert('1.0', "Please Check the SECOND Address Format", "warning")
                return
            else:
                #convert string to int for iteration
                from_address_int = int(from_address_str, 16)
                to_address_int = int(to_address_str, 16)

                if to_address_int < from_address_int:
                    self.tx_text.insert('1.0', "Please Check the RANGE, first address is greater than second address", "warning")
                    return

                #using existing command, i.e load address and read bytes
                for i in range(from_address_int, to_address_int + 1):
                    #assume the most sig byte is to the leftmost, thus byteorder
                    current_address_str = i.to_bytes(4, byteorder = "big").hex()
                    for lower_bits in current_address_str:
                        result_byte = bytes([int(lower_bits, 16) | byte_mask[0]]) #ORing operation
                        self.send(result_byte)

                    read_byte_command = DROP_DOWN_MENU["READ BYTE"]
                    self.send(read_byte_command)

        #printing and logging
        bytes_in_str = ' '.join(self.byte_buffer)
        self.tx_text.insert('end', bytes_in_str)
        logging.info("Sent Data Packet Overview: {}".format(bytes_in_str))
        self.byte_buffer.clear()

    def start(self):
        self.main_frame.mainloop()

    def disable_edit_menu(self):
        self.edit_menu.entryconfig(0, state = "disabled")
        self.edit_menu.entryconfig(1, state = "disabled")

    def enable_edit_menu(self):
        self.edit_menu.entryconfig(0, state = "normal")
        self.edit_menu.entryconfig(1, state = "normal")



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

    def config_port(self):
        current_port = self.serial_handle.serial.port

        popup = tk.Toplevel()
        popup.title("Change Serial Port")
        popup.resizable(0,0)

        msg = tk.Message(popup, text = "Select from Existing Port:", width = 150)
        msg.grid(row = 0, column = 0, pady = (20, 0), padx = (30, 0))

        port_var = tk.StringVar()
        port_var.set(current_port)
        ports_list = [i.device for i in serial.tools.list_ports.comports()]

        ports_dropdown = tk.OptionMenu(popup, port_var, *(sorted(ports_list)))
        ports_dropdown.config(bg = "light grey")
        ports_dropdown.grid(row = 0, column = 1, pady = (20, 0), padx = (0, 30))

        def assign_port():
            self.serial_handle.serial.port = port_var.get()

        buttons = tk.Frame(popup)
        buttons.grid(row = 1, column = 0, columnspan = 2)
        confirm = tk.Button(buttons, text = "Confirm", bg = "light grey", command = assign_port)
        cancel = tk.Button(buttons, text = "Cancel", bg = "light grey", command = popup.destroy)
        confirm.grid(row = 0, column = 0, padx = 10, pady = 15)
        cancel.grid(row = 0, column = 1, padx = 15)

        confirm.bind("<Enter>", lambda event: confirm.configure(bg = "white"))
        confirm.bind("<Leave>", lambda event: confirm.configure(bg = "light grey"))
        cancel.bind("<Enter>", lambda event: cancel.configure(bg = "white"))
        cancel.bind("<Leave>", lambda event: cancel.configure(bg = "light grey"))
        ports_dropdown.bind("<Enter>", lambda event: ports_dropdown.configure(bg = "white"))
        ports_dropdown.bind("<Leave>", lambda event: ports_dropdown.configure(bg = "light grey"))

        popup.rowconfigure(0, weight=1)
        popup.columnconfigure(0, weight=1)


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

    def clear_rx_console(self):
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

    #range address mode
    def add_range_command_widgets(self):
        self.entry_box.grid_forget()

        self.range_var_1 = tk.StringVar()
        self.range_var_2 = tk.StringVar()

        self.range_entry_box_1 = tk.Entry(self.command_frame, textvariable = self.range_var_1)
        self.range_entry_box_1.grid(row = 0, column = 1, ipadx = 60, padx = 15, sticky = "NSEW")
        self.prompt = tk.Label(self.command_frame, text = "TO")
        self.prompt.grid(row = 0, column = 2)
        self.range_entry_box_2 = tk.Entry(self.command_frame, textvariable = self.range_var_2)
        self.range_entry_box_2.grid(row = 0, column = 3, ipadx = 60, padx = 15, sticky = "NSEW")

        self.tx_apply_button.grid(row = 0, column = 4, padx = 15, ipadx = 10)

        self.command_frame.columnconfigure(3, weight=5)

        self.RANGE_MODE = True

    #return to normal one entry box mode
    def remove_range_command_widgets(self):
        self.range_entry_box_1.grid_forget()
        self.range_entry_box_2.grid_forget()
        self.prompt.grid_forget()

        self.entry_box.grid(row = 0, column = 1, ipadx = 60, padx = 15, sticky = "NSEW")
        self.tx_apply_button.grid(row = 0, column = 1, padx = 15, ipadx = 10, sticky = "E")

        self.command_frame.columnconfigure(3, weight=0)
        self.RANGE_MODE = False

    def to_hexdump(self, canonical: bool):
        if self.raw_data == '':
            self.raw_data = self.rx_text.get('1.0', "end-1c")

        if (self.RANGE_MODE) and (len(self.raw_data) != 0):
            hexdump = []
            index = 0 # initial index to traverse raw_data
            address_count = 16 # display address for every 16 returned bytes (advance address by 1 hex unit)
            address_temp = []
            concat_count = 0 # two bytes should concatonate together under non-cononical formatting
            concat_temp  = []
            canonical_text = []

            while index < len(self.raw_data):
                if address_count >= 16:
                    if len(hexdump):
                        hexdump[-1] = hexdump[-1] + '\n'
                    else:
                        hexdump.append("")
                    #parse address
                    address_temp.extend(self.raw_data[index+1: index+24: 3])
                    index += 24

                    address = ''.join(address_temp)    # use join to improve performance over str + str
                    hexdump.append(address)

                    address_temp.clear()
                    address_count = 0
                else:
                    index += 24  #skip current address

                #parse based on whether user wants canonical repersentation or not
                if canonical:
                    data = self.raw_data[index: index+2]
                    hexdump.append(data)

                    if address_count == 0:
                        canonical_text.append("|")
                    try:
                        temp_text = bytes.fromhex(data).decode("ascii")
                        temp_text = re.sub(r'[^\x21-\x7e]',r'.', temp_text)
                        canonical_text.append(temp_text)
                        print(canonical_text)
                    except UnicodeDecodeError:
                        canonical_text.append('.')

                    if address_count == 15: #next line
                        canonical_text.append("|")
                        hexdump.append("".join(canonical_text))
                        canonical_text.clear()
                    index += 3
                else:
                    concat_temp.append(self.raw_data[index: index+2])
                    concat_count += 1
                    index += 3

                    if concat_count >= 2:
                        hexdump.append("".join(concat_temp))
                        concat_temp.clear()
                        concat_count = 0
                #endif
                address_count += 1
            #endwhile
            if len(concat_temp):
                hexdump.append("".join(concat_temp))    #add in what was left in concat_temp buffer

            if len(canonical_text):
                canonical_text.insert(0, " " * (16-address_count) * 3)
                canonical_text.append("|")
                hexdump.append("".join(canonical_text)) #add in what was left in canonical_text buffer

            self.clear_rx_console()
            self.rx_text.configure(state = "normal")
            self.rx_text.insert('end', " ".join(hexdump)) #[1:] to get rid of newline
            self.rx_text.configure(state = "disabled")
