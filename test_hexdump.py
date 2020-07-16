import re

class Fake():
    def __init__(self):
        self.raw_data = "20 20 20 20 20 20 22 22 08 20 20 20 20 20 20 22 23 09 20 20 20 20 "\
                        "20 20 22 24 0a 20 20 20 20 20 20 22 25 0b 20 20 20 20 20 20 22 26 "\
                        "0c 20 20 20 20 20 20 22 27 0d 20 20 20 20 20 20 22 28 0e 20 20 20 "\
                        "20 20 20 22 29 10 20 20 20 20 20 20 22 2a 11 20 20 20 20 20 20 22 "\
                        "2b 12 20 20 20 20 20 20 22 2c 13 20 20 20 20 20 20 22 2d 14 20 20 "\
                        "20 20 20 20 22 2e 15 20 20 20 20 20 20 22 2f 16 20 20 20 20 20 20 "\
                        "23 20 17 20 20 20 20 20 20 23 21 18 20 20 20 20 20 20 23 22 19 20 "\
                        "20 20 20 20 20 23 23 1a 20 20 20 20 20 20 23 24 1b 20 20 20 20 20 "\
                        "20 23 25 1c 20 20 20 20 20 20 23 26 41 20 20 20 20 20 20 23 27 42 "\
                        "20 20 20 20 20 20 23 28 43 20 20 20 20 20 20 23 29 44 20 20 20 20 "\
                        "20 20 23 2a 45 20 20 20 20 20 20 23 2b 7e 20 20 20 20 20 20 23 2c "\
                        "7f 20 20 20 20 20 20 23 2d 80 20 20 20 20 20 20 23 2e 81 20 20 20 "\
                        "20 20 20 23 2f 82 20 20 20 20 20 20 24 20 83 20 20 20 20 20 20 24 "\
                        "21 84 20 20 20 20 20 20 24 22 85"
        self.RANGE_MODE = True
        self.to_hexdump(True)

    def to_hexdump(self, canonical):
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
                    address = ''.join(address_temp)    # use join to improve performance over str + str
                    hexdump.append(address)

                    address_temp.clear()
                    address_count = 0
                    index += 24
                else:
                    #skip current address
                    index += 24

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
                address_count += 1
            #endwhile
            if len(concat_temp):
                hexdump.append("".join(concat_temp))    #add in what was left in concat_temp buffer

            if len(canonical_text):
                canonical_text.insert(0, " " * (16-address_count) * 3)
                canonical_text.append("|")
                hexdump.append("".join(canonical_text)) #add in what was left in canonical_text buffer

            print(" ".join(hexdump))

if __name__ == '__main__':
    a = Fake()
