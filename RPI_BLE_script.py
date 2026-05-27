#!/usr/bin/env/python3

from __future__ import annotations
from datetime import datetime
import array
import ast
import json
import logging
import os
import sys
from typing import Union   # For Python 3.9.2

import bt_ble_hm
from daylight_intensity_calculator import get_intensity

SCRIPT_NAME, _ = os.path.splitext(os.path.basename(__file__))
logging.basicConfig(filename=SCRIPT_NAME,  level=logging.DEBUG, format='%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s', datefmt='%Y/%m/%d %H:%M:%S')

CMD_COUNTER_LOG: str = "bt_ble_command_counter.log"
CRC_POLY: str        = 0xEDB88320
KEY_FILE: str        = "bt_ble_secret_key.key"

def get_secret_key() -> str:
    try:
        with open(KEY_FILE, 'r') as k:
            key: str =  k.read().strip()
    except FileNotFoundError:
        print(f"ERROR: Encryption key file '{KEY_FILE}' is missing")
        sys.exit(1)
    return key

def ticks_to_time() -> str:
    now: str = datetime.now()
    h: str = now.strftime("%H")
    m: str = now.strftime("%M")
    s: str = now.strftime("%S")
    t: str = h+m+s
    return t

def encrypt(cmd: str) -> str:
    key: str = get_secret_key()
    assert isinstance(cmd, str), "Input not string"
    lenght: int = len(cmd)
    key_lenght: int = len(key)
    cmd_bytes: str = str.encode(cmd)
    new: str = ''
    for i, b in enumerate(cmd_bytes):
        key_index: int = i % key_lenght
        key_mask: int = ord(key[key_index]) & 0b00011111
        new += ''.join(chr(b ^ key_mask))
    return new
 
def setup_crc_table() -> array.array[int]:
    CRC_table: array.array[int] = array.array('L')
    for byte in range(256):
        crc: int = 0
        for bit in range(8):
            if (byte ^ crc) & 1:
                crc = (crc >> 1) ^ CRC_POLY
            else:
                crc >>= 1
            byte >>= 1
        CRC_table.append(crc)
    return CRC_table

def add_crc(cmd: str) -> str:
    CRC_table = setup_crc_table()
    def crc32(string: str) -> int:
        v = 0xffffffff
        for c in string:
            v: int = CRC_table[(ord(c) ^ v) & 0xff] ^ (v >> 8)
        return -1 - v

    crc_val = str(hex(crc32(cmd + ':') & 0xffffffff)[2:])
    return cmd + ':' + crc_val


ABSOLUTE_INDEX_ID: str      = 'AIX' # RGB, Start, Offset
ZONE_INDEX_ID: str          = 'ZIX' # RGB, Zone_list_lengt, Zones
GRADIENT_ID: str            = 'GRA' # RGB, Start, Offset
TIME_SYNC_ID: str           = 'TSY' #
BRIGHTNESS_ID: str          = 'BRI' # RGB
DAYLIGHT_ID: str            = 'DAL' # RGB
CUSTOM_ID: str              = 'CDP' # RGB, PWM
TEST_ID: str                = 'TST'
ENCRYPT_ID: str             = 'ENC'
ALARM_ID: str               = 'ALM'
COSTUM_DISPLAY_ID: str      = 'DSP'
ALARM_DELETE_ID: str        = 'ALD'
SPARKEL_CONTROL_ID: str     = 'SCI'
CLOCK_PWM: str              = 'CPM' # PWM between 0x0000 and 0xFFFF



class Command_Message():
    def __init__(self):
        pass
        #self.command_counter = self.fetch_command_counter()

    def send_message(self, message: str, encrypted: str) -> int:
        hm: BT_BLE_HM  = bt_ble_hm.BT_BLE_HM()
        if not hm.error:
            hm.transmit(encrypted)
            logging.info(f'Message sent: {message}, {encrypted}')
            hm.disconnect()
            self.store_command_counter(self.command_counter)
            return 0
        else:
            logging.error(f'Message not sent: {message}, {encrypted} due to {hm.error}.')
            return 1 

    def quit(self) -> None:
        self.store_command_counter(self.command_counter)

    
    def command_code_formatter(self, cmd: str) -> str:
        try:
            cur: int = int(self.command_counter[cmd])
        except KeyError:
            cur: int = 0
        cur += 1
        self.command_counter[cmd] = cur
        return cmd + ('000000' + str(cur))[-6:]


    def compose_message(self, message: str) -> str:
        message: str = add_crc(message)
        encrypted: str = encrypt(message)
        return encrypted


    def format_command(self, args: list[str]) -> Union[str, None]:
        self.command_counter: dict[str, Union[str, int]]  = self.fetch_command_counter()
        if len(args) <= 1:
            print(f'''

            Usage: {args[0]} options
                -a   (AIX000) | Absolute indexing. Args: start, stop, RGB
                -z   (ZIX000) | Zone indexing. Args: zone, RGB
                -g   (GRA000) | Gradient. Args: start, stop, RGB
                -t   (TSY000) | Time Sync. Args: TIME (HhMmSs)
                -b   (BRI000) | Brightness. Args: RGB
                -b   (DAL000) | Daylight. Args: RGB
                -c   (CDF000) | Custom display. Args: STR, PWM
                -r   (TST000) | Raw string.
                -e   (ENC000) | Raw string, encoded.
                -al  (ALM000) | Abs or Rel, severity, 
                -ald (ALM000) | Abs or Rel, severity, 

                ''')
            return None
        if len(args) > 1:
            command: str = args[1]
            if command == '-a':
                cmd_code: str = self.command_code_formatter(ABSOLUTE_INDEX_ID)
                start: str = str(args[2])
                end: str = str(args[3])
                data: str = str(args[4])
                message: str = cmd_code + ':' + start + ':' + end + ':' + data
                return message

            if command == '-z':
                cmd_code: str = self.command_code_formatter(ZONE_INDEX_ID)
                zone: str = str(args[2])
                data: str = str(args[3])
                message: str = cmd_code + ':' + zone + ':' + data
                return message
            
            if command == '-g':
                cmd_code: str = self.command_code_formatter(GRADIENT_ID)
                data: str = ''
                ds: str = args[2:]
                for d in ds:
                    data = data + ':' + d
                message: str = cmd_code + data
                print(f'format_command:: cmd_code: {cmd_code}, message: {message}, data: {data}, ds: {ds}')
                return message

            if command == '-g?':
                print(f'To set gradient: -g START<0-n>* RrGgBb<000000-ffffff>* MIDDLE_n0<0-n>* RrGgBb<000000-ffffff>* MIDDLE_n1<0-n>* RrGgBb<000000-ffffff>* END<0-n>* RrGgBb<000000-ffffff>*.') 
                print(f'Example: <-g 0 00ff00 10 ff0000 20 0000ff>. * Are required. Any number of middle points are accepted so long there are as many RrGgBb values')
                return None

            if command == '-t':
                cmd_code: str = self.command_code_formatter(TIME_SYNC_ID)
                data: str  = ticks_to_time()
                message: str = cmd_code + ':' + data
                return message

            if command == '-b':
                cmd_code: str = self.command_code_formatter(BRIGHTNESS_ID)
                data: str = str(args[2])
                message: str = cmd_code + ':' + data
                return message

            if command == '-d':
                cmd_code: str = self.command_code_formatter(DAYLIGHT_ID)
                data: str = str(args[2])
                message: str = cmd_code + ':' + data
                return message

            if command == '-c':
                cmd_code: str = self.command_code_formatter(CUSTOM_ID)
                data: str = str(args[2])
                pwm: str = str(args[3])
                message: str = cmd_code + ':' + data + ':' + pwm
                return message

            if command == '-sp':
                cmd_code: str = self.command_code_formatter(SPARKEL_CONTROL_ID)
                on_off: str = str(args[2])
                if len(args) < 3:
                    freq: int = 1
                else:
                    freq: int = str(args[3])
                if len(args) < 4:
                    para: int = 0
                else:
                    para: int = str(args[4])
                message: str = cmd_code + ':' + on_off + ':' + freq + ':' + para
                return message


            if command == '-r':
                cmd_code: str = self.command_code_formatter(TEST_ID)
                data: str = str(args[2])
                message: str =  data
                return message
            if command == '-al':
                cmd_code: str = self.command_code_formatter(ALARM_ID)
                abs_or_rel: str = str(args[2])
                sev: str = str(args[3])
                data: str = str(args[4])
                if len(args) > 5:
                    data: str = data + ':' + str(args[5])
                if len(args) > 6:
                    data: str = data + ':' + str(args[6])
                message: str = cmd_code + ':' + abs_or_rel + ':' + sev + ':' + data
                return message

            if command == '-al?':
                print(f'To set alarm: -al ABS_or_REL<a/r>* SEV TIME_STAMPS<000000-235959>* DURATION<1-n>* PERSISTANCE<0/1>.') 
                print(f'Example: <-al a 0 1234 10 0>. * Are required. Defaults: DURATION: 10, PERSISTANCE: 0.')
                return None
            if command == '-ald':
                cmd_code: str = self.command_code_formatter('ALD')
                abs_or_rel: str = str(args[2])
                sev: str = str(args[3])
                data: str = str(args[4])
                message: str = cmd_code + ':' + abs_or_rel + ':' + sev + ':' + data
                return message
            if command == '-p':
                cmd_code: str = self.command_code_formatter(CLOCK_PWM)
                pwm: str = args[2]
                try:
                    pwm_val: int = int(pwm, base=0)
                except ValueError:
                    w_m: str = f"Command CLOCK_PWM 'CPM' takes int type argument between 0x0000 and 0xFFFF not {pwm}."
                    logging.warning(w_m)
                    print(w_m)
                    sys.exit(1)
                if pwm_val < 0 or pwm_val > 0xffff:
                    w_m: str = f"Command CLOCK_PWM 'CPM' takes argument between 0x0000 and 0xFFFF not {pwm}."
                    print(w_m)
                    logging.warning(w_m)
                    return None
                else:
                    message: str = cmd_code + ':' + str(pwm)
                    return message
            if command == "--daylight-adjust":
                cmd_code: str = self.command_code_formatter(CLOCK_PWM)
                pwm_val: int = get_intensity()
                if pwm_val < 0 or pwm_val > 0xffff:
                    logging.warning(f"Command CLOCK_PWM 'CPM' takes argument between 0x0000 and 0xFFFF not {pwm}.")
                    return None
                else:
                    message: str = cmd_code + ':' + str(pwm_val)
                    return message

            else:
                logging.warning(f'Command not parsed: {args}')
                print(f'Command not parsed: {args}')
                return None

    def store_command_counter(self, command_counter):
        with open('bt_ble_command_counter.log', 'w') as f:
            f.write(repr(command_counter))
            #json.dump(command_counter, f)

    def fetch_command_counter(self) -> dict[str, Union[str, int]]:
        try:
            with open(CMD_COUNTER_LOG, 'r') as f:
                command_counter: dict[str, Union[str, int]] = ast.literal_eval(f.read())

        except FileNotFoundError:
            m_w: str = f"file '{CMD_COUNTER_LOG}' was not present so it was created.  If client device has command counters that are non-zero commands will not be accepted on client side."
            logging.warning(m_w)
            print(f"WARNING: ", m_w)
            command_counter: dict[str, Union[str, int]] = {}
            command_list: list[str] = [ABSOLUTE_INDEX_ID, ZONE_INDEX_ID, GRADIENT_ID, TIME_SYNC_ID, BRIGHTNESS_ID, DAYLIGHT_ID, CUSTOM_ID, TEST_ID, ALARM_ID, ALARM_DELETE_ID, SPARKEL_CONTROL_ID, CLOCK_PWM]
            for c in command_list:
                command_counter[c] = 0
            self.store_command_counter(command_counter)
        return command_counter


def main() -> None:
    cmd_message: Command_Message = Command_Message()
    message:str = cmd_message.format_command(sys.argv)
    return_value: int = -1
    if message != None:
        encrypted: str = cmd_message.compose_message(message)
        print(f"{sys.argv[0]}: Sending message '{message}' - '{encrypted}...'", end='')
        return_value: int = cmd_message.send_message(message, encrypted)
    if (return_value == 0):
        print(f"{sys.argv[0]}: Done.")
    else:
        print(f"{sys.argv[0]}: send_message returned error({return_value}).")
 

if __name__ == "__main__":
    main()
    sys.exit(0)   



#!/usr/bin/env/python3

import bt_ble_hm
import sys
from datetime import datetime
import logging
import json
import array

logname = str(sys.argv[0])[:-3] + '.log'
logging.basicConfig(filename=logname,  level=logging.DEBUG, format='%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s', datefmt='%Y/%m/%d %H:%M:%S')

CMD_COUNTER_LOG = "bt_ble_command_counter.log"
CRC_POLY = 0xEDB88320
KEY_FILE = "bt_ble_secret_key.key"

def get_secret_key():
    with open(KEY_FILE, 'r') as k:
        key =  k.read().strip()
    return key

def ticks_to_time():
    now = datetime.now()
    h = now.strftime("%H")
    m = now.strftime("%M")
    s = now.strftime("%S")
    t = h+m+s
    # dd/mm/YY H:M:S format
    print(f"ticks_to_time::  {h}, {m}, {s}, {t}")
    return t

def encrypt(cmd):
    key = get_secret_key()
    assert isinstance(cmd, str), "Input not string"
    lenght = len(cmd)
    key_lenght = len(key)
    cmd_bytes = str.encode(cmd)
    new = ''
    for i, b in enumerate(cmd_bytes):
        key_index = i % key_lenght
        key_mask = ord(key[key_index]) & 0b00011111
        new += ''.join(chr(b ^ key_mask))
    print(f'encrypt:: clean: {cmd},  new: {new}\n')
    return new
 
def setup_crc_table():
    CRC_table = array.array('L')
    for byte in range(256):
        crc = 0
        for bit in range(8):
            if (byte ^ crc) & 1:
                crc = (crc >> 1) ^ CRC_POLY
            else:
                crc >>= 1
            byte >>= 1
        CRC_table.append(crc)
    return CRC_table

def add_crc(cmd):
    CRC_table = setup_crc_table()
    def crc32(string):
        v = 0xffffffff
        for c in string:
            v = CRC_table[(ord(c) ^ v) & 0xff] ^ (v >> 8)
        return -1 - v

    crc_val = str(hex(crc32(cmd + ':') & 0xffffffff)[2:])
    print(f'add_crc:: cmd: {cmd}, crc_val: {crc_val}, ')
    return cmd + ':' + crc_val


def command_code_formatter(cmd):
    try:
        cur = int(command_counter[cmd])
    except KeyError:
        cur = 0
    cur += 1
    command_counter[cmd] = cur
    return cmd + ('000000' + str(cur))[-6:]



def run_command():
    if len(sys.argv) <= 1:
        print(f'''

        Usage: {sys.argv[0]} options
            -a   (AIX000) | Absolute indexing. Args: start, stop, RGB
            -z   (ZIX000) | Zone indexing. Args: zone, RGB
            -g   (GRA000) | Gradient. Args: start, stop, RGB
            -t   (TSY000) | Time Sync. Args: TIME (HhMmSs)
            -b   (BRI000) | Brightness. Args: RGB
            -b   (DAL000) | Daylight. Args: RGB
            -c   (CDF000) | Custom display. Args: STR, PWM
            -r   (TST000) | Raw string.
            -e   (ENC000) | Raw string, encoded.
            -al  (ALM000) | Abs or Rel, severity, 
            -ald (ALM000) | Abs or Rel, severity, 

            ''')
        return -1
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == '-a':
            cmd_code = command_code_formatter('AIX')
            start = str(sys.argv[2])
            end = str(sys.argv[3])
            data = str(sys.argv[4])
            message = cmd_code + ':' + start + ':' + end + ':' + data
            return message
        if command == '-z':
            cmd_code = command_code_formatter('ZIX')
            zone = str(sys.argv[2])
            data = str(sys.argv[3])
            message = cmd_code + ':' + zone + ':' + data
            return message
        if command == '-g':
            cmd_code = command_code_formatter('GRA')
            data = ''
            ds = sys.argv[2:]
            for d in ds:
                data = data + ':' + d
            message = cmd_code + data
            print(f'run_command:: cmd_code: {cmd_code}, message: {message}, data: {data}, ds: {ds}')
            return message
        if command == '-g?':
            print(f'To set gradient: -g START<0-n>* RrGgBb<000000-ffffff>* MIDDLE_n0<0-n>* RrGgBb<000000-ffffff>* MIDDLE_n1<0-n>* RrGgBb<000000-ffffff>* END<0-n>* RrGgBb<000000-ffffff>*.') 
            print(f'Example: <-g 0 00ff00 10 ff0000 20 0000ff>. * Are required. Any number of middle points are accepted so long there are as many RrGgBb values')
            return -1
        if command == '-t':
            cmd_code = command_code_formatter('TSY')
            data  = ticks_to_time()
            message = cmd_code + ':' + data
            return message
        if command == '-b':
            cmd_code = command_code_formatter('BRI')
            data = str(sys.argv[2])
            message = cmd_code + ':' + data
            return message
        if command == '-d':
            cmd_code = command_code_formatter('DAL')
            data = str(sys.argv[2])
            message = cmd_code + ':' + data
            return message
        if command == '-c':
            cmd_code = command_code_formatter('CDP')
            data = str(sys.argv[2])
            pwm = str(sys.argv[3])
            message = cmd_code + ':' + data + ':' + pwm
            return message

        if command == '-sp':
            cmd_code = command_code_formatter('SCI')
            on_off = str(sys.argv[2])
            if len(sys.argv) < 3:
                freq = 1
            else:
                freq = str(sys.argv[3])
            if len(sys.argv) < 4:
                para = 0
            else:
                para = str(sys.argv[4])
            message = cmd_code + ':' + on_off + ':' + freq + ':' + para
            return message


        if command == '-r':
            cmd_code = command_code_formatter('TST')
            data = str(sys.argv[2])
            message =  data
            return message
        if command == '-al':
            cmd_code = command_code_formatter('ALM')
            abs_or_rel = str(sys.argv[2])
            sev = str(sys.argv[3])
            data = str(sys.argv[4])
            if len(sys.argv) > 5:
                data = data + ':' + str(sys.argv[5])
            if len(sys.argv) > 6:
                data = data + ':' + str(sys.argv[6])
            message = cmd_code + ':' + abs_or_rel + ':' + sev + ':' + data
            return message
        if command == '-al?':
            print(f'To set alarm: -al ABS_or_REL<a/r>* SEV TIME_STAMPS<000000-235959>* DURATION<1-n>* PERSISTANCE<0/1>.') 
            print(f'Example: <-al a 0 1234 10 0>. * Are required. Defaults: DURATION: 10, PERSISTANCE: 0.')
            return -1
        if command == '-ald':
            cmd_code = command_code_formatter('ALD')
            abs_or_rel = str(sys.argv[2])
            sev = str(sys.argv[3])
            data = str(sys.argv[4])
            message = cmd_code + ':' + abs_or_rel + ':' + sev + ':' + data
            return message

        else:
            logging.warning(f'Command not parsed: {sys.argv}')
            print(f'Command not parsed: {sys.argv}')
            return -1
            
    
def compose_message(message):
    message = add_crc(message)
    print(f"main:: message: {message}")
    encrypted = encrypt(message)
    return encrypted
        

def send_message(message, encrypted):
    hm = bt_ble_hm.BT_BLE_HM()
    if not hm.error:
        hm.transmit(encrypted)
        logging.info(f'Message sent: {message}, {encrypted}')
        with open('bt_ble_command_counter.log', 'w') as f:
            json.dump(command_counter, f)
            #print(f'Updating command_counter.log: {command_counter} \n')
        hm.disconnect()
        return 1
    else:
        logging.error(f'Message not sent: {message}, {encrypted} due to {hm.error}.')
        return -1


 

if __name__ == "__main__":
    try:
        with open(CMD_COUNTER_LOG, 'r') as f:
            command_counter = json.loads(f.read())
    except FileNotFoundError:
        m_w = f"file '{CMD_COUNTER_LOG}' was not present so it was created. If client device has command counters that are non-zero commands will not be accepted on client side."
        logging.warning(m_w)
        print(f"WARNING: ", m_w)
        command_counter = {}
        command_list = ['AIX', 'ZIX', 'GRA', 'TSY', 'BRI', 'DAL', 'CDP', 'TST', 'ALM']
        for c in command_list:
            command_counter[c] = 0
        with open('bt_ble_command_counter.log', 'w') as f:
            json.dump(command_counter, f)
    
    
    
    message = run_command()
    if message != -1:
        encrypted = compose_message(message)
        send_message(message, encrypted)
