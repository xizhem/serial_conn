import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk
import serial.tools.list_ports
import threading
import time
import logging
import os
import re

DROP_DOWN_MENU = {
"DUMP MEMORY": b'\x00',
"LOAD ADDRESS": b'\x20',      #0x2-
"LOAD DATA": b'\x40',         #0x4-
"READ BYTE": b'\xE0',    #0xE-
"READ DATA RANGE" : b'\x20'   #FF is just the same as loading, this command composite Load Address and READ BYTE
}

S_MODES = {
"Writing": 1,
"Reading": 2,
}

STD_BAUD = [
110, 300, 600, 1200, 2400, 4800, 9600,
14400, 19200, 38400, 57600, 115200,
128000, 256000
]

STD_STOPBITS = {
'1'  : serial.STOPBITS_ONE,
'1.5': serial.STOPBITS_ONE_POINT_FIVE,
'2'  : serial.STOPBITS_TWO
}

STATUS_BAR_TEMPLATE = "serialMonitorAddr: "

class DebuggerInter():
    def __init__(self, serial_handle, log_name):
        self.serial_handle = serial_handle      # Object <ReaderThread>
        self.response_start_time = 0
        self.byte_buffer = []
        self.update_buffer = []
        self.raw_data = ''
        self.TIMING = False
        self.RANGE_MODE = False
        self.flush_done = True
        self.rx_first_byte = True
        self.s_widgets_to_remove = []

        #tkinter setup
        self.main_frame = tk.Tk()
        self.main_frame.title("UART Debugger Console")

        self.tab_parent = ttk.Notebook(self.main_frame)
        self.simplified_tab = ttk.Frame(self.tab_parent)
        self.advanced_tab = ttk.Frame(self.tab_parent)

        self.tab_parent.add(self.simplified_tab, text = "Simplified Mode")
        self.tab_parent.add(self.advanced_tab, text = "Advanced Mode")

        self.tab_parent.grid(row = 0, column = 0, sticky = "NSEW")

        #top menu bar
        self.menubar = tk.Menu(self.main_frame)
        self.main_frame.config(menu = self.menubar)

        self.config_menu = tk.Menu(self.menubar, tearoff = 0)
        self.menubar.add_cascade(label = "Config", menu = self.config_menu)
        self.config_menu.add_command(label = "Change Serial Settings", command = lambda: self.config_port())

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


        #------Simplified Mode------#
        self.s_command_frame = ttk.LabelFrame(self.simplified_tab, text = "Commands")
        self.s_command_frame.grid(row = 1, column = 0, sticky = "NSEW", pady = (10, 0), padx = 5)
        self.s_command_var = tk.StringVar()

        s_column_num = 0
        for k,v in S_MODES.items():
            self.b = ttk.Radiobutton(self.s_command_frame, text = k, variable = self.s_command_var, value = v)
            self.b.grid(row = 0, column = s_column_num, sticky = "NSEW", ipady = 15, padx= (15, 0))
            s_column_num += 1

        def onChange_radiobutton(*args):
            if self.s_command_var.get() == "1":
                self.add_s_write_widgets()
            elif self.s_command_var.get() == "2":
                self.add_s_read_widgets()
        self.s_command_var.trace("w", onChange_radiobutton)

        self.s_control_frame = ttk.LabelFrame(self.simplified_tab, text = "Controls")
        self.s_control_frame.grid(row = 2, column = 0, pady = 15, padx = 5, sticky = "NSEW")

        #------Advanced Mode------#
        #receive box
        self.rx_console = tk.LabelFrame(self.advanced_tab, text = "Receive Data", padx=5, pady=10)
        self.rx_console.grid(row = 1, column = 0, sticky = "NSEW")
        self.rx_text = scrolledtext.ScrolledText(self.rx_console, state = "disabled")
        self.rx_text.grid(row = 0, column = 0, sticky = "NSEW")
        self.rx_text.tag_config("warning", foreground = "red")

        #transimit box
        self.tx_console = tk.LabelFrame(self.advanced_tab, text = "Transmit Data", padx=5, pady=10)
        self.tx_console.grid(row = 2, column = 0, sticky = "NSEW")
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
            if command == "READ DATA RANGE":
                if self.RANGE_MODE == False:
                    self.add_range_command_widgets()
                    self.enable_edit_menu()
            else:
                if self.RANGE_MODE == True: #switch from range mode to other mode
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

        self.tx_apply_button = tk.Button(self.command_frame, text = "APPLY",
                                    bg = "light grey", command = lambda: self.processApplyButton())
        self.tx_apply_button.grid(row = 0, column = 1, padx = 15, ipadx = 10, sticky = "E")

        self.tx_send_button = tk.Button(self.tx_console, text = "SEND",
                                    bg="light blue", command = lambda: self.processSendButton())
        self.tx_send_button.grid(row = 2, column = 0, pady = 15, ipadx = 50, ipady = 2)

        self.tx_apply_button.bind("<Enter>", lambda event: self.tx_apply_button.configure(bg = "white"))
        self.tx_apply_button.bind("<Leave>", lambda event: self.tx_apply_button.configure(bg = "light grey"))
        self.tx_send_button.bind("<Enter>", lambda event: self.tx_send_button.configure(bg = "white"))
        self.tx_send_button.bind("<Leave>", lambda event: self.tx_send_button.configure(bg = "light blue"))

        #bottome status bar
        self.status_var = tk.StringVar(value = STATUS_BAR_TEMPLATE + "NaN")
        self.status_bar = tk.Label(self.tx_console, textvariable = self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row = 3, column = 0, sticky = "NSWE")

        #resizing factor
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        self.advanced_tab.columnconfigure(0, weight=1)
        self.advanced_tab.rowconfigure((1, 2), weight=1)

        self.simplified_tab.columnconfigure(0, weight=1)
        for i in range(s_column_num):
            self.s_command_frame.columnconfigure(i, weight=1)

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
            byte_str = byte_str.strip() #delete trailing newlines and whitespaces
            try:
                byteToSend = bytes.fromhex(byte_str)
                self.send(byteToSend)
            except ValueError as e:
                #echo error to the Console
                self.tx_text.delete('1.0', "end")
                self.tx_text.insert('1.0', e, "warning")
                logging.warning("Transimtted Address/Data has format error")
        #prepare rx console for upcoming rx data
        self.sent_packages_routines()

    #"apply" button onClick callback
    def processApplyButton(self):
        command = self.command_var.get()
        if command == "Choose a Command" or command not in DROP_DOWN_MENU:
            return
        byte_mask = DROP_DOWN_MENU[command]

        #prepare tx/rx console for upcoming rx data(do not clear in read data range command)
        self.tx_text.delete('1.0', "end")

        bytes_in_str = ''
        if (command == "DUMP MEMORY") or (command == "READ BYTE"):
            result_byte = byte_mask
            self.send(result_byte)

        elif (command == "LOAD ADDRESS") or (command == "LOAD DATA"):
            input_byte_str = self.entry_box_var.get()
            try:
                int(input_byte_str, 16)
            except ValueError as e:
                self.tx_text.insert('1.0', "Please Check that Address contains valid HEX only", "warning")
                return
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
                try:
                    from_address_int = int(from_address_str, 16)
                    to_address_int = int(to_address_str, 16)
                except ValueError as e:
                    self.tx_text.insert('1.0', "Please Check that Address contains valid HEX only", "warning")
                    return

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
        bytes_in_str = self.sent_packages_routines()
        self.tx_text.insert('end', bytes_in_str)

    def sent_packages_routines(self):
        """ a routine that is used both by send button and apply button:
            to prepare/clear the rx console for upcoming data,
            logging the bytes into the backlog,
            and check the address pointed to by serialMonitorAddr currently
            Return the sent packages in str
        """
        self.flush_update_buffer()
        self.clear_rx_console()
        bytes_in_str = ' '.join(self.byte_buffer)
        if len(bytes_in_str):
            logging.info("Sent Data Packet Overview: {}".format(bytes_in_str))
            self.byte_buffer.clear()

            m = re.match(r".*2(.) 2(.) 2(.) 2(.) 2(.) 2(.) 2(.) 2(.)", bytes_in_str)
            if m:
                address = []
                for i in range(1,9):
                    address.append(m.group(i))
                self.status_var.set(STATUS_BAR_TEMPLATE + "".join(address))
        return bytes_in_str

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
            #a buffer to write chunks of data to improve performance
            self.update_buffer.append(data.hex())
            #force inserting text in simplified mode
            if len(self.update_buffer) > 32:
                self.rx_text.configure(state = "normal")
                self.update_buffer.append("") #insert a space
                self.rx_text.insert('end', " ".join(self.update_buffer))
                self.rx_text.configure(state = "disabled")
                self.update_buffer.clear()

    def flush_update_buffer(self):
        if len(self.update_buffer):
            self.rx_text.configure(state = "normal")
            self.rx_text.insert('end', " ".join(self.update_buffer))
            self.rx_text.configure(state = "disabled")
            self.update_buffer.clear()
            self.flush_done = True

    def config_port(self):
        current_port = self.serial_handle.serial.port
        current_baud = self.serial_handle.serial.baudrate
        current_stopbits = self.serial_handle.serial.stopbits

        popup = tk.Toplevel()
        popup.title("Settings")
        popup.resizable(0,0)

        #centering
        width = 350
        height = 270
        root_width = self.main_frame.winfo_width()
        root_height = self.main_frame.winfo_height()

        x = self.main_frame.winfo_x()
        y = self.main_frame.winfo_y()
        x = x + (root_width/2 - width/2)
        y = y + (root_height/2 - height/2)
        popup.geometry("%dx%d+%d+%d" % (350, 220 , x, y))

        f = tk.Frame(popup, borderwidth =1, relief=tk.SOLID)
        f.grid(row = 0, column = 0, ipadx = 10, pady = (20,0), ipady = 5)
        #ports
        port_msg = tk.Message(f, text = "Port:")
        port_msg.grid(row = 0, column = 0, pady = (10, 0), padx = (20, 0), sticky = "W")

        port_var = tk.StringVar()
        port_var.set(current_port)
        ports_list = [i.device for i in serial.tools.list_ports.comports()]

        ports_dropdown = tk.OptionMenu(f, port_var, *(sorted(ports_list)))
        ports_dropdown.config(bg = "light grey")
        ports_dropdown.grid(row = 0, column = 1, pady = (10, 0), padx = (110, 0), sticky = "E")


        #baud rates
        port_msg = tk.Message(f, text = "Baud Rate:")
        port_msg.grid(row = 1, column = 0, pady = (10, 0), padx = (20, 0), sticky = "W")

        baud_var = tk.StringVar()
        baud_var.set(current_baud)

        baud_dropdown = tk.OptionMenu(f, baud_var, *STD_BAUD)
        baud_dropdown.config(bg = "light grey")
        baud_dropdown.grid(row = 1, column = 1, pady = (10, 0), sticky = "E")

        #stop bits
        stopbits_msg = tk.Message(f, text = "Stop Bits:")
        stopbits_msg.grid(row = 2, column = 0, pady = (10, 0), padx = (20, 0), sticky = "W")

        stopbits_var= tk.StringVar()
        stopbits_var.set(current_stopbits)

        stopbits_dropdown = tk.OptionMenu(f, stopbits_var, *STD_STOPBITS)
        stopbits_dropdown.config(bg = "light grey")
        stopbits_dropdown.grid(row = 2, column = 1, pady = (10, 0), sticky = "E")


        def assign():
            self.serial_handle.serial.port = port_var.get()
            self.serial_handle.serial.baudrate = baud_var.get()
            self.serial_handle.serial.stopbits = STD_STOPBITS[stopbits_var.get()]
            popup.destroy()

        buttons = tk.Frame(popup)
        buttons.grid(row = 1, column = 0, columnspan = 2)
        save = tk.Button(buttons, text = "Save", bg = "light grey", command = assign)
        cancel = tk.Button(buttons, text = "Cancel", bg = "light grey", command = popup.destroy)
        save.grid(row = 0, column = 0, ipadx = 10, padx = 10, pady = 15)
        cancel.grid(row = 0, column = 1,ipadx = 5, padx = 15)

        save.bind("<Enter>", lambda event: save.configure(bg = "white"))
        save.bind("<Leave>", lambda event: save.configure(bg = "light grey"))
        cancel.bind("<Enter>", lambda event: cancel.configure(bg = "white"))
        cancel.bind("<Leave>", lambda event: cancel.configure(bg = "light grey"))
        ports_dropdown.bind("<Enter>", lambda event: ports_dropdown.configure(bg = "white"))
        ports_dropdown.bind("<Leave>", lambda event: ports_dropdown.configure(bg = "light grey"))
        baud_dropdown.bind("<Enter>", lambda event: baud_dropdown.configure(bg = "white"))
        baud_dropdown.bind("<Leave>", lambda event: baud_dropdown.configure(bg = "light grey"))
        stopbits_dropdown.bind("<Enter>", lambda event: stopbits_dropdown.configure(bg = "white"))
        stopbits_dropdown.bind("<Leave>", lambda event: stopbits_dropdown.configure(bg = "light grey"))

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
        self.flush_done = False

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
        self.rx_first_byte = True

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
        if s_read_flag:
            self.s_rx_text.configure(state = "normal")
            self.s_rx_text.insert('end', "No Response from FPGA", "warning")
            self.s_rx_text.configure(state = "disabled")
        self.status_var.set(STATUS_BAR_TEMPLATE + "NaN")

    def add_s_write_widgets(self):
        #clear up the control frame
        self.remove_s_control_widgets()

        self.write_address_var = tk.StringVar()
        self.data_var = tk.StringVar()

        self.left_frame = ttk.Frame(self.s_control_frame)
        self.left_frame.grid(row = 0, column = 0, pady = (15,35))
        self.right_frame = ttk.Frame(self.s_control_frame)
        self.right_frame.grid(row = 0, column = 1, pady = (15,5), padx = (0, 30))

        self.address_prompt = ttk.Label(self.left_frame, text = "Address:")
        self.address_prompt.grid(row = 0, column = 0, pady = (0,5), columnspan = 2)
        self.hex_prompt_1 = ttk.Label(self.left_frame, text = "0x")
        self.hex_prompt_1.grid(row = 1, column = 0, sticky = "E",  padx = (15,0))
        self.address_entry = ttk.Entry(self.left_frame, textvariable = self.write_address_var)
        self.address_entry.grid(row = 1, column = 1)

        self.data_prompt = ttk.Label(self.left_frame, text = "Data:")
        self.data_prompt.grid(row = 2, column = 0, pady= (20, 5), columnspan = 2)
        self.hex_prompt_2 = ttk.Label(self.left_frame, text = "0x")
        self.hex_prompt_2.grid(row = 3, column = 0, sticky = "E")
        self.data_entry = ttk.Entry(self.left_frame, textvariable = self.data_var)
        self.data_entry.grid(row = 3, column = 1)

        self.progress_var = tk.StringVar(value = "Status:")
        self.progress_prompt = ttk.Label(self.right_frame, textvariable = self.progress_var)
        self.progress_prompt.grid(row = 0, column = 2)
        self.progress = ttk.Progressbar(self.right_frame, orient="horizontal",
                                  length=150, mode="determinate")
        self.progress.grid(row = 1, column = 2)

        self.s_send = ttk.Button(self.right_frame, text = "Send", command = lambda: self.process_s_write_button())
        self.s_send.grid(row = 2, column = 2, pady = 15)

        self.s_control_frame.columnconfigure((0,1), weight=1)
    def add_s_read_widgets(self):
        #clear up the control frame
        self.remove_s_control_widgets()

        self.read_address_var_1 = tk.StringVar()
        self.read_address_var_2 = tk.StringVar()

        self.upper_frame = ttk.Frame(self.s_control_frame)
        self.upper_frame.grid(row = 0, column = 0, padx = 10, sticky = "NSEW")
        self.lower_frame = ttk.LabelFrame(self.s_control_frame, text = "Settings")
        self.lower_frame.grid(row = 1, column = 0, pady = 10, padx = 10, sticky = "NSEW")
        self.lower_L_frame = ttk.Frame(self.lower_frame)
        self.lower_L_frame.grid(row = 0, column = 0, padx = 30, pady = (0, 10), sticky = "NSEW")
        self.lower_R_frame = ttk.Frame(self.lower_frame)
        self.lower_R_frame.grid(row = 0, column = 1, pady = (0, 10), sticky = "NSEW")

        #upper_frame
        self.s_rx_text = scrolledtext.ScrolledText(self.upper_frame, state = "disabled")
        self.s_rx_text.grid(row = 0, column = 0, pady = 10, sticky = "NSEW")
        self.s_rx_text.tag_config("warning", foreground = "red")

        self.busy_bus = ttk.Progressbar(self.upper_frame, orient="horizontal", mode="indeterminate")

        #lower_frame
        self.read_mode_var = tk.StringVar()
        self.single_button = ttk.Radiobutton(self.lower_L_frame, text = "Single Address",
                                        variable = self.read_mode_var, value = 1)
        self.single_button.grid(row = 0, column = 0, sticky = "NSEW")
        self.range_button = ttk.Radiobutton(self.lower_L_frame, text = "Range Address",
                                        variable = self.read_mode_var, value = 2)
        self.range_button.grid(row = 1, column = 0, sticky = "NSEW")

        self.address_prompt = ttk.Label(self.lower_R_frame, text = "Address:")
        self.address_entry_1 = ttk.Entry(self.lower_R_frame, textvariable = self.read_address_var_1)
        self.to_label = ttk.Label(self.lower_R_frame, text = "TO")
        self.address_entry_2 = ttk.Entry(self.lower_R_frame, textvariable = self.read_address_var_2)
        self.read_button = ttk.Button(self.lower_R_frame, text = "Read", command = lambda: self.process_s_read_button())

        def onChange_read_mode(*args):
            for widget in self.lower_R_frame.winfo_children():
                widget.grid_forget()
            if self.read_mode_var.get() == "1":
                self.address_prompt.grid(row = 0, column = 0, pady = 5)
                self.address_entry_1.grid(row = 1, column = 0)
                self.read_button.grid(row = 2, column = 0, pady = (10,0))
            elif self.read_mode_var.get() == "2":
                self.address_prompt.grid(row = 0, column = 1, pady = 5)
                self.address_entry_1.grid(row = 1, column = 0)
                self.to_label.grid(row = 1, column = 1)
                self.address_entry_2 .grid(row = 1, column = 2)
                self.read_button.grid(row = 2, column = 1, pady = (10,0))

        self.read_mode_var.trace("w", onChange_read_mode)

        self.s_control_frame.columnconfigure(0, weight=1)
        self.upper_frame.columnconfigure(0, weight=1)
        self.lower_frame.columnconfigure((0,1), weight=1)
        self.lower_frame.rowconfigure(0, weight=1)
        self.lower_L_frame.rowconfigure(0, weight=1)
        self.lower_R_frame.rowconfigure(0, weight=1)

    def remove_s_control_widgets(self):
        for widget in self.s_control_frame.winfo_children():
            widget.destroy()

    def process_s_read_button(self):
        address_1 = self.read_address_var_1.get()
        address_2 = self.read_address_var_2.get()
        mode = self.read_mode_var.get()

        #clear text box
        self.s_rx_text.config(state = "normal")
        self.s_rx_text.delete("1.0", "end")
        self.s_rx_text.configure(state = "disabled")

        def helper():
            text = self.tx_text.get("1.0", "end")
            if "Please Check" in text:
                self.s_rx_text.configure(state = "normal")
                self.s_rx_text.insert('end', text, "warning")
                self.s_rx_text.configure(state = "disabled")
                return False
            return True

        # need a worker thread to copy text from advacned mode to
        # simplified mode bc tkinter cannot be blocked and wait for copying
        def worker(mode):
            self.busy_bus.grid(row = 1, column = 0, sticky = "NSEW")
            self.busy_bus.start(10)
            self.read_button.config(state = "disabled")
            while True:
                if self.TIMING and self.response_elapsed() > 10:
                    break

                if self.flush_done:
                    result = ""
                    if mode == "1":
                        result = self.rx_text.get("1.0", "end-1c")[-2:]
                    elif mode == "2":
                        self.to_hexdump(False)
                        result = self.rx_text.get("1.0", "end-1c")
                    self.s_rx_text.configure(state = "normal")
                    self.s_rx_text.insert('end', result)
                    self.s_rx_text.configure(state = "disabled")
                    break
                time.sleep(0.5)

            self.busy_bus.stop()
            self.busy_bus.grid_forget()
            self.read_button.config(state = "normal")

        if mode == "1":
            self.command_var.set("LOAD ADDRESS")
            self.entry_box_var.set(address_1)
            self.processApplyButton()
            if not helper():
                return
            self.command_var.set("READ BYTE")
            self.processApplyButton()

        elif mode == "2":
            self.command_var.set("READ DATA RANGE")
            self.range_var_1.set(address_1)
            self.range_var_2.set(address_2)
            self.processApplyButton()
            if not helper():
                return

        self.current_worker = threading.Thread(target = worker, args=[mode])
        self.current_worker.start()

    def process_s_write_button(self):
        self.progress["value"] = 0
        self.progress["maximum"] = 4

        address = self.write_address_var.get()
        data = self.data_var.get()

        #use existing advacned mode abstraction
        def helper():
            self.progress_var.set("Status: Busy")
            self.processApplyButton()
            self.progress["value"] += 1

            time.sleep(0.1)
            send_text = self.tx_text.get("1.0", "end")
            receive_text =  self.rx_text.get("1.0", "end")

            if "Please Check" in send_text:
                self.progress_var.set("Status: Please Check the Address/Data Format")
                self.progress["value"] = 0
                return False
            elif send_text.lower() == receive_text.lower():
                self.progress["value"] += 1
                return True
            else:
                self.progress_var.set("Status: Unknown Error")
                self.progress["value"] = 0
                return False

        self.command_var.set("LOAD ADDRESS")
        self.entry_box_var.set(address)
        if not helper():
            return
        self.command_var.set("LOAD DATA")
        self.entry_box_var.set(data)
        if not helper():
            return
        #complete
        self.progress_var.set("Status: Complete")

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
            self.rx_text.insert('end', " ".join(hexdump))
            self.rx_text.configure(state = "disabled")
