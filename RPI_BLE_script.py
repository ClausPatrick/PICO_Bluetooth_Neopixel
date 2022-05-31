#!/usr/bin/env/python3

import bt_ble_hm
import sys
from datetime import datetime
import logging
import json
import array

logname = str(sys.argv[0])[:-3] + '.log'
logging.basicConfig(filename=logname,  level=logging.DEBUG, format='%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s', datefmt='%Y/%m/%d %H:%M:%S')


try:
    with open('bt_ble_command_counter.log', 'r') as f:
        command_counter = json.loads(f.read())
        #print(f'logs: {command_counter} \n')
except FileNotFoundError:
    command_counter = {}
    command_list = ['AIX', 'ZIX', 'GRA', 'TSY', 'BRI', 'DAL', 'CDP', 'TST', 'ALD']
    for c in command_list:
        command_counter[c] = 0
    with open('bt_ble_command_counter.log', 'w') as f:
        json.dump(command_counter, f)
        #print(f'Updating command_counter.log: {command_counter} \n')


with open('bt_ble_secret_key.key', 'r') as k:
    key =  k.read()
    #print(f'key: {key}')

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



CRC_POLY = 0xEDB88320
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


def add_crc(cmd):
    def crc32(string):
        v = 0xffffffff
        for c in string:
            v = CRC_table[(ord(c) ^ v) & 0xff] ^ (v >> 8)
            #print(f'add_crc:: c: {c}, v: {v}')
        return -1 - v
    crc_val = str(hex(crc32(cmd + ':') & 0xffffffff)[2:])
    print(f'add_crc:: cmd: {cmd}, crc_val: {crc_val}, ')
    #print(cmd + ':' + crc_val)
    return cmd + ':' + crc_val
    #return cmd+crc_val


def command_code_formatter(cmd):
    #cur = command_counter[command_list[cmd]]
    cur = command_counter[cmd]
    cur += 1
    command_counter[cmd] = cur
    return cmd + ('000000' + str(cur))[-6:]



def run_command():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == '-a':
            cmd_code = command_code_formatter('AIX')
            start = str(sys.argv[2])
            end = str(sys.argv[3])
            data = str(sys.argv[4])
            message = cmd_code + ':' + start + ':' + end + ':' + data
        if command == '-z':
            cmd_code = command_code_formatter('ZIX')
            zone = str(sys.argv[2])
            data = str(sys.argv[3])
            message = cmd_code + ':' + zone + ':' + data
        if command == '-g':
            cmd_code = command_code_formatter('GRA')
            data = ''
            ds = sys.argv[1:]
            for d in ds:
                data = data + ':' + d
                print(data)
            message = cmd_code + data
            print(message)
        if command == '-g?':
            print(f'To set gradient: -g START<0-n>* RrGgBb<000000-ffffff>* MIDDLE_n0<0-n>* RrGgBb<000000-ffffff>* MIDDLE_n1<0-n>* RrGgBb<000000-ffffff>* END<0-n>* RrGgBb<000000-ffffff>*.') 
            print(f'Example: <-g 0 00ff00 10 ff0000 20 0000ff>. * Are required. Any number of middle points are accepted so long there are as many RrGgBb values'
        if command == '-t':
            cmd_code = command_code_formatter('TSY')
            data  = ticks_to_time()
            message = cmd_code + ':' + data
        if command == '-b':
            cmd_code = command_code_formatter('BRI')
            data = str(sys.argv[2])
            message = cmd_code + ':' + data
        if command == '-d':
            cmd_code = command_code_formatter('DAL')
            data = str(sys.argv[2])
            message = cmd_code + ':' + data
        if command == '-c':
            cmd_code = command_code_formatter('CDP')
            data = str(sys.argv[2])
            pwm = str(sys.argv[3])
            message = cmd_code + ':' + data + ':' + pwm
        if command == '-r':
            cmd_code = command_code_formatter('TST')
            data = str(sys.argv[2])
            message =  data
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
        if command == '-al?':
            print(f'To set alarm: -al ABS_or_REL<a/r>* SEV TIME_STAMPS<000000-235959>* DURATION<1-n>* PERSISTANCE<0/1>.') 
            print(f'Example: <-al a 0 1234 10 0>. * Are required. Defaults: PERSISTANCE: 0, DURATION: 10.')
        if command == '-ald':
            cmd_code = command_code_formatter('ALD')
            abs_or_rel = str(sys.argv[2])
            sev = str(sys.argv[3])
            data = str(sys.argv[4])
            message = cmd_code + ':' + abs_or_rel + ':' + sev + ':' + data

        else:
            logging.warning(f'Command not parsed: {sys.argv}')
            print(f'Command not parsed: {sys.argv}')
            

        message = add_crc(message)
        print(f"main:: message: {message}")
        encrypted = encrypt(message)

        hm = bt_ble_hm.BT_BLE_HM()
        if hm.error == None:
            hm.transmit(encrypted)
            logging.info(f'Message sent: {message}, {encrypted}')
            with open('bt_ble_command_counter.log', 'w') as f:
                json.dump(command_counter, f)
                #print(f'Updating command_counter.log: {command_counter} \n')
        else:
            logging.error(f'Message not sent: {message}, {encrypted} due to {hm.error}.')


    else:
        print(f'''

        Missing argument for message to be sent.
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

            ''')


run_command()
