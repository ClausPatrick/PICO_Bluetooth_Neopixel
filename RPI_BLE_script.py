#!/usr/bin/env/python3

import bt_ble_hm
import sys
from datetime import datetime
import logging
import json

logname = str(sys.argv[0])[:-3] + '.log'
logging.basicConfig(filename=logname,  level=logging.DEBUG, format='%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s', datefmt='%Y/%m/%d %H:%M:%S')

try:
    with open('bt_ble_command_counter.log', 'r') as f:
        command_counter = json.loads(f.read())
        #print(f'logs: {command_counter} \n')
except FileNotFoundError:
    command_counter = {}
    command_list = ['AIX', 'ZIX', 'GRA', 'TSY', 'BRI', 'DAL', 'CDP', 'TST']
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

def command_code_formatter(cmd):
    #cur = command_counter[command_list[cmd]]
    cur = command_counter[cmd]
    cur += 1
    command_counter[cmd] = cur
    return cmd + ('000000' + str(cur))[-6:]

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
        start = str(sys.argv[2])
        end = str(sys.argv[3])
        data = str(sys.argv[4])
        message = cmd_code + ':' + start + ':' + end + ':' + data
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
    if command == '-e':
        cmd_code = command_code_formatter('ENC')
        data = str(sys.argv[2])
        data_enc = encrypt(data)
        message = cmd_code + ':' + data_enc


    print(f"main:: message: {message}")
    encrypted = encrypt(message)

    hm = bt_ble_hm.BT_BLE_HM()
    hm.transmit(encrypted)
    logging.info(f'Message sent: {message}, {encrypted}')

    with open('bt_ble_command_counter.log', 'w') as f:
        json.dump(command_counter, f)
        #print(f'Updating command_counter.log: {command_counter} \n')

else:
    print(f'''

    Missing argument for message to be sent.
        -a (AIX000) | Absolute indexing. Args: start, stop, RGB
        -z (ZIX000) | Zone indexing. Args: zone, RGB
        -g (GRA000) | Gradient. Args: start, stop, RGB
        -t (TSY000) | Time Sync. Args: TIME (HhMmSs)
        -b (BRI000) | Brightness. Args: RGB
        -b (DAL000) | Daylight. Args: RGB
        -c (CDF000) | Custom display. Args: STR, PWM
        -r (TST000) | Raw string.
        -e (ENC000) | Raw string, encoded.

        ''')
