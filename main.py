import array, utime, time
from machine import Pin, Timer, I2C
import rp2
from rp2 import PIO, StateMachine, asm_pio
from time import sleep
import re
import random
import CD4094_class
import json
import hashlib
import MAC_hash_list
import private_key


# Loading external values.
key = private_key.key
allowed_central_list = MAC_hash_list.hashlist
NUM_LEDS = 57


with open('command_counter.json', 'r') as f:
    command_counter = json.loads(f.read())
    print(f'command_counter: {command_counter} \n')


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


# Setting up HW peripheries.   
led_onboard = machine.Pin(25, machine.Pin.OUT)
led_onboard.value(1)

uart = machine.UART(0, 9600, tx=Pin(12), rx=Pin(13), bits=8, parity=None, stop=1)
cd = CD4094_class.CD4094()


led_ok = machine.PWM(machine.Pin(5))
led_err = machine.PWM(machine.Pin(6))
draw_sw = machine.Pin(1, machine.Pin.IN, machine.Pin.PULL_UP)
led_ok.freq(1000)
led_err.freq(1000)
led_ok.duty_u16(65535)
led_err.duty_u16(0)



# PIO program to interface with ws2812
@asm_pio(sideset_init=PIO.OUT_LOW, out_shiftdir=PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
def ws2812():
    # fmt: off
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)               .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")   .side(1)    [T1 - 1]
    jmp("bitloop")          .side(1)    [T2 - 1]
    label("do_zero")
    nop()                   .side(0)    [T2 - 1]
    wrap()
    
# Create the StateMachine with the ws2812 program, outputting on Pin(0).
sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(0))

# Start the StateMachine, it will wait for data on its FIFO.
sm.active(1)


class Clock():
    '''Keeping track of time, synchronising to central, formatting time such it can be displayed.'''    
    def __init__(self):
        self.ticks = 0
        self.tick_quarter = 0
        self.sync_buffer = 0
        self.sec_counter = 0
        self.display_pwm = 0x00ff
        self.enable_display_daylight_adjustment = True
        self.is_synced = False
        
    @staticmethod
    def time_formatter(ticks):
        '''Var ticks (0 to 24*60) to timeformat HhMm. '''        
        assert ticks <= (24 * 60)
        h = '00' + str((ticks) // 60)
        m = '00' + str((ticks) % 60)
        return h[-2:] + m[-2:]
        
    
    
    def ticker(self):
        '''Var ticks counts from 0 to 24*60 for each minute. Var tick_quarter is actually seconds. '''        
        def ticker_func(timer):            
            if self.tick_quarter == 0:
                self.ticks = (self.ticks + 1) % (24 * 60)
                time_formatted = self.time_formatter(self.ticks)                    
                cd.transmit(time_formatted, red=0, pwm_duty = (self.display_pwm//1))
            self.tick_quarter = (self.tick_quarter + 1) % 60
        self.ticker_timer = Timer()
        self.ticker_timer.init(freq=1, mode=Timer.PERIODIC, callback=ticker_func)  
    
    @staticmethod
    def time_to_ticks(data):
        c_sync = (data[:4][0:2], data[:4][2:4])
        f_sync = int(data[-2:])
        ticks_new = (int(c_sync[0]) * 60) + int((c_sync[1]))
        print(f'time_to_ticks:: data: {data}, c_sync: {c_sync}, f_sync: {f_sync}, ticks_new: {ticks_new}')
        return (ticks_new, f_sync)
    
    def clock_sync(self, data):
        print(f'clock_sync:: data: {data}')
        assert len(data) == 6 and isinstance(data, str)
        ticks, tick_quarter = self.time_to_ticks(data)
        print(f'clock_sync:: data:{data}, ticks: {ticks}, tick_quarter: {tick_quarter}')
        self.sync_buffer = data
        self.ticks = ticks
        self.tick_quarter = tick_quarter
        time_formatted = self.time_formatter(self.ticks)
        cd.transmit(time_formatted, red=0, pwm_duty=(self.display_pwm//1))
        
    def set_pwm(self, data):
        pwm = int(data)
        assert (data >= 0) and (data <= 0xffff)
        self.display_pwm = data
        time_formatted = self.time_formatter(self.ticks)
        cd.transmit(time_formatted, red=0, pwm_duty = (self.display_pwm//1))
        print(f'PWM set to: {data}')
        
    def custom_write(self, data, pwm=None):
        if pwm != None:
            self.set_pwm(pwm)
        cd.transmit(data, red=0, pwm_duty=self.display_pwm//1)
        
        
    


class LED_admin():
    def __init__(self, NUM_LEDS=57):
        self.NUM_LEDS = NUM_LEDS
        self.daylight_factor = 0xffffff
        self.daylight_list = (255,255,255)
        self.brightness_factor = 0x7f7f7f
        self.brightness_list = (0x7f,0x7f,0x7f)
        self.arr = array.array("I", [0 for _ in range(NUM_LEDS)])
        self.arr_opened = self.arr[:]
        self.rgb_list = array.array("I", [0 for _ in range(NUM_LEDS)])

        self.z_00 = [i for i in range(3, 7)] # AUX UT
        self.z_01 = [i for i in range(7, 23)] # AUX T
        self.z_02 = [i for i in range(23, 31)] # AUX L
        self.z_ff = [i for i in range(32, 46+1)] # JM_SPOT
        self.z_list = [self.z_00, self.z_01, self.z_02, self.z_ff]
        self.z_all = self.z_00 + self.z_01 + self.z_02 + self.z_ff
        self.sparkel_level = None
        

    @staticmethod
    def rgb_formatter(data):
        '''Array of 3 RGB data converted to fit Neopixel format (GgRrBb where character-pair is 1 byte size). Error return -1
        if shit goes sideways.
        '''
        if len(data) == 3:
            return sum([i<<j for i, j in zip(data, (8, 16, 0))])
        else:
            return -1      

    @staticmethod
    def rgb_reformatter(data):
        '''Opposite of rgb_formatter. Takes either int value or hex formatted string and parses it into (r, g, b) tuple with ints.'''
        if isinstance(data, int):
            s = ('000000' + str(hex(data)[2:]))[-6:] # Ensuring string lenght = 6.      
        elif isinstance(data, str):
            s = ('000000' + data)[-6:]
        else:
            raise ValueError
        rgb = (int(s[2]+s[3], 16), int(s[0]+s[1], 16), int(s[4]+s[5], 16))
        return rgb

    def output_to_chain(self, data):
        sm.put(data, 8)
    
    def rgb_scaling(self):
        '''Performing a weighted sum of rgb_list, brightness and daylight. Result written into array arr.'''
        for i in range(NUM_LEDS):
            s = ('000000' + str(hex(self.rgb_list[i]))[2:])[-6:]
            #print(f's: {s}, {type(s)}')
            s0 = str(hex(min(int(int(s[0:2], 16) * (self.brightness_list[0] / 127) * (self.daylight_list[0] / 255)), 255)))[2:]
            s1 = str(hex(min(int(int(s[2:4], 16) * (self.brightness_list[1] / 127) * (self.daylight_list[1] / 255)), 255)))[2:]
            s2 = str(hex(min(int(int(s[4:6], 16) * (self.brightness_list[2] / 127) * (self.daylight_list[2] / 255)), 255)))[2:]
            self.arr[i]  = int(('00' + s0)[-2:] + ('00' + s1)[-2:] + ('00' + s2)[-2:], 16)

    def set_brightness(self, brightness='7f7f7f'):
        self.brightness_factor = brightness
        brightness_reformed = self.rgb_reformatter(brightness)
        assert brightness_reformed != -1
        self.brightness_list = brightness_reformed
        self.rgb_scaling()
        self.output_to_chain(self.arr)

    def set_daylight(self, brightness=0xffffff):
        self.daylight_factor = brightness
        brightness_reformed = self.rgb_reformatter(brightness)
        assert brightness_reformed != -1
        self.daylight_list = brightness_reformed
        self.rgb_scaling()
        self.output_to_chain(self.arr)
        if clock.enable_display_daylight_adjustment:
            pwm_adj = (int(brightness, 16) & 0x00ffff) | 0b11
            print(f'set_daylight:: pwm_adj: {pwm_adj}, {hex(pwm_adj)}')
            clock.set_pwm(pwm_adj)


    def drawer_closed(self):
        self.output_to_chain(self.arr)
    
    def drawer_opened(self):
        self.arr_opened = self.arr[:]
        self.arr_opened[11] = self.rgb_formatter((random.randrange(85)*2, random.randrange(85)*2, random.randrange(85)*3))
        self.arr_opened[12] = self.rgb_formatter((random.randrange(85)*2, random.randrange(85)*3, random.randrange(85)*2))
        self.arr_opened[13] = self.rgb_formatter((random.randrange(85)*3, random.randrange(85)*2, random.randrange(85)*2))    
        self.output_to_chain(self.arr_opened)        

    def print_list(self):
        print('print_list::\n')
        print(self.__dict__)
        for ix, dx in enumerate(data):
            a = self.rgb_reformatter(self.arr[ix])
            b = self.rgb_reformatter(self.rgb_list[ix])
            print(f'    arr: {a}, rgb: {b}')

    def insist_int(self, rgb_in):
        '''Sanity check'''
        if isinstance(rgb_in, int):
            rgb_in = ('000000' + str(hex(data)[2:]))[-6:]
            #print(f'insist_int:: int: rgb_in: {rgb_in}')
        elif isinstance(rgb_in, str):
            #print(f'insist_int:: str: rgb_in: {rgb_in}')
            rgb_in = rgb_in[2:4] + rgb_in[0:2] + rgb_in[4:6]                        
        elif isinstance(rgb_in, (list, tuple)):
            rgb_in = self.rgb_formatter(rgb_in)
            rgb_in = ('000000' + str(hex(rgb_in)[2:]))[-6:]
            #print(f'insist_int:: list: rgb_in: {rgb_in}')
            
        else:
            raise ValueError
        rgb_reform = rgb_in[0:2] + rgb_in[2:4] + rgb_in[4:6]
        rgb = int(rgb_reform, 16)
        #print(f'insist_int:: else: rgb_in: {rgb_in}, rgb_reform: {rgb_reform}, rgb: {rgb}, {hex(rgb)}')
        return rgb

    def set_absolute(self, start, end, rgb_str):
        '''Write RGB value on range of LEDs from start to end.'''
        rgb = self.insist_int(rgb_str)
        for i in range(start, end):
            #print(f'set_absolute:: rgb: {rgb}, i: {i}, NUM_LEDS: {NUM_LEDS}')
            if i <= NUM_LEDS:
                self.rgb_list[i] = rgb
        self.rgb_scaling()
        self.output_to_chain(self.arr)
        print(f'set_absolute:: rgb: {rgb}, {hex(rgb)}')
        
    def set_gradient(self, start, end, rgb_str):
        '''Write RGB value on range of LEDs from start to end.'''
        rgb = self.insist_int(rgb_str)
        for i in range(start, end):
            #print(f'set_absolute:: rgb: {rgb}, i: {i}, NUM_LEDS: {NUM_LEDS}')
            if i <= NUM_LEDS:
                self.rgb_list[i] = rgb
        self.rgb_scaling()
        self.output_to_chain(self.arr)
        print(f'set_gradient:: rgb: {rgb}, {hex(rgb)}')

    def set_zone(self, zone_nr, rgb_str):
        '''Write RGB value on range of LEDs assigned to specific zone.'''
        rgb = self.insist_int(rgb_str)
        for z in self.z_list[zone_nr]:
            self.rgb_list[z] = rgb
        self.rgb_scaling()
        self.output_to_chain(self.arr)

    def sparkel(self, f='h', l='h', s='h'):
        new_freq = 2
        freq_list_full = (2, 1.64, 1.25, 1.117, 1, 0.8, 0.5, 0.33, 0.1)
        freq_list = freq_list_full[:]
        def sparkel_func(timer):
            level = self.sparkel_level                        
            if level == None:
                freq_list = freq_list_full
            if level == 'Low':
                freq_list = freq_list_full[3:]
            if level == 'Medium':
                freq_list = freq_list_full[-3:]
            if level == 'High':
                freq_list = freq_list_full[2:-2]
            if draw_sw.value() == 0:
                arr_copy = self.arr[:]
                bling = (255, 220, 160)
                rand_index = random.randrange(self.NUM_LEDS) # Btw 0 and NUM_LEDS (incl)
                rand_len = 2 + random.randrange(20) # Btw 2 and 22 (incl)
                rand_time = 4 + random.randrange(12) # Btw 4 and 16 (incl)
                for i in range(rand_len): # Btw 2 and 22 (incl)
                    ii = int(i/4 + 1)
                    rand_value = (bling[random.randrange(3)]//ii, bling[random.randrange(3)]//ii,bling[random.randrange(3)]//ii)
                    rand_index_mult = random.randrange(self.NUM_LEDS)
                    arr_copy[rand_index] = self.rgb_formatter(rand_value) # Btw 0 and NUM_LEDS (incl)
                    self.output_to_chain(arr_copy)
                    utime.sleep_ms(rand_time) # Btw 4 and 16 (incl)
                self.output_to_chain(self.arr)
                new_freq = freq_list[random.randrange(len(freq_list))]
                self.sparkel_timer.init(freq=new_freq, mode=Timer.PERIODIC, callback=sparkel_func)
        self.sparkel_timer = Timer()
        self.sparkel_timer.init(freq=2, mode=Timer.PERIODIC, callback=sparkel_func)     

class Alarm():
    def __init__(self):
        self.abs_time = 0
        self.rel_time = 0
        self.severity = 3
        
    
    def indicator(self, severity=3):
        if severity == 0:
            print(f'###Alarm:: indicator:: {self.abs_time}, {self.rel_time}, {severity}###')
        if severity == 1:
            print(f'***Alarm:: indicator:: {self.abs_time}, {self.rel_time}, {severity}***')
        if severity == 2:
            print(f'---Alarm:: indicator:: {self.abs_time}, {self.rel_time}, {severity}---')
        if severity == 3:
            print(f'...Alarm:: indicator:: {self.abs_time}, {self.rel_time}, {severity}...')
            
    def set_alarm(self, severity=3, abs_time=None, rel_time=None):
        if severity != None:
            self.severity = severity
        current_ticks = clock.ticks
        if abs_time != None:
            self.abs_time = int(clock.time_to_ticks(abs_time)[0])
            many_ticks_to_alarm = self.abs_time
    
            ticks_counter = abs(((many_ticks_to_alarm - current_ticks) * 60) - 60)
            print(f'set_alarm::: abs_time:: many_ticks_to_alarm: {many_ticks_to_alarm}, current_ticks: {current_ticks}, ticks_counter: {ticks_counter}')
        elif rel_time != None:
            self.rel_time = int(rel_time)
            ticks_counter = self.rel_time
            
        else:
            ticks_counter = 10
            print(f'set_alarm:: No time specified. Going with default: {ticks_counter} sec')
        timer_freq = 1 / (ticks_counter+1)
        def alarm_counter_timer_func(timer):
            print(f'alarm_counter_timer_func:: {abs_time}, {rel_time}, {severity}, {timer_freq}')
            self.indicator(severity=int(severity))
            
        self.alarm_timer = Timer()
        self.alarm_timer.init(freq=timer_freq, mode=Timer.ONE_SHOT, callback=alarm_counter_timer_func)
        print(f'set_alarm:: Timer set for: {clock.time_formatter(many_ticks_to_alarm)}, now: {clock.time_formatter(current_ticks)}, {abs_time}, {rel_time}, {severity}, {timer_freq}- done')
        

        
        
clock = Clock()
clock.ticker()
alarm = Alarm()


# Init routine:
pixels = LED_admin()
pixels.sparkel()
pixels.set_zone(zone_nr=0, rgb_str='402005')
utime.sleep_ms(5)
pixels.set_zone(zone_nr=1, rgb_str='402005')
utime.sleep_ms(5)
pixels.set_zone(zone_nr=2, rgb_str='402005')
utime.sleep_ms(5)
pixels.set_zone(zone_nr=3, rgb_str='402005')
utime.sleep_ms(5)

drawer_opened = 0


def draw_routine(pin):
    global drawer_opened
    utime.sleep_ms(10)
    if drawer_opened != draw_sw.value():
        drawer_opened = draw_sw.value()
        led_err.duty_u16(int(65535 * draw_sw.value()))
        if draw_sw.value():
            pixels.drawer_opened()
        else: 
            pixels.drawer_closed()
   
draw_sw.irq(trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING, handler=draw_routine)

# Inbound Bluetooth packets.
# Setting up variables handling data from packets.
is_connected = False
is_MAC = False
is_data = False
data_change = False
connect_syntax = b"OK+CONN:"
disconnect_syntax = b"OK+LOST:"
inbound = False
payload_list = []
wholeframe = bytes()
led_err.duty_u16(int(0))
led_ok.duty_u16(int(65535))

ABSOLUTE_INDEX_ID = 'AIX' # RGB, Start, Offset
ZONE_INDEX_ID = 'ZIX' # RGB, Zone_list_lengt, Zones
GRADIENT_ID = 'GRA' # RGB, Start, Offset
TIME_SYNC_ID = 'TSY' # 
BRIGHTNESS_ID = 'BRI' # RGB
DAYLIGHT_ID = 'DAL' # RGB
CUSTOM_ID = 'CDP' # RGB, PWM
TEST_ID = 'TST'
ENCRYPT_ID = 'ENC'
ALARM_ID = 'ALM'


class BT_processor():
    key = private_key.key
    allowed_central_list = MAC_hash_list.hashlist

    def __init__(self):
        self.MAC_check = False
        self.CRC_check = False
        self.command_counter_check = False
        self.command_counter = command_counter
        self.payload_split = []
        self.payload_decrypted = ''
        with open('command_counter.json', 'r') as f:
            self.command_counter = json.loads(f.read())
            print(f'command_counter: {self.command_counter} \n')

        CRC_POLY = 0xEDB88320
        self.CRC_table = array.array('L')
        for byte in range(256):
            crc = 0
            for bit in range(8):
                if (byte ^ crc) & 1:
                    crc = (crc >> 1) ^ CRC_POLY
                else:
                    crc >>= 1
                byte >>= 1
            self.CRC_table.append(crc)

    def error_handler(self, error_type, data):
        print(f'BT_processor::: error_handler:: error_type: {error_type}, {data}')
        led_err.duty_u16(int(65535))
        led_ok.duty_u16(int(0))
        
    def MAC_whitelist_check(self, MAC_address):
        self.MAC_check = False
        if hashlib.sha256(MAC_address).digest() in self.allowed_central_list:
            print(f'MAC_whitelist_check:: Central address verified, {MAC_address}')
            self.MAC_check = True

    def decrypt(self, cmd):
        assert isinstance(cmd, bytes), "Input not Bytes"
        lenght = len(cmd)
        key_lenght = len(self.key)
        cmd_bytes = cmd
        new = ''
        for i, b in enumerate(cmd_bytes):
            key_index = i % key_lenght
            key_mask = ord(self.key[key_index]) & 0b00011111
            new += ''.join(chr(b ^ key_mask))
        print(f'decrypt:: clean: {cmd},  new: {new}')    
        return new 

    def check_crc(self):
        def crc32(string):
            v = 0xffffffff
            for c in string:
                v = CRC_table[(ord(c) ^ v) & 0xff] ^ (v >> 8)
            return -1 - v
        d = self.payload_split
        cmd = self.payload_decrypted
        crc_received = int(d[-1], 16)

        message = cmd[:-len(d[-1])]
        crc_result = crc32(message) & 0xffffffff
        self.CRC_check = crc_result == crc_received
        print(f'check_crc:: cmd: {self.payload_decrypted}, rx: {crc_received}, m: {message}, res: {crc_result}, ?: {self.CRC_check}')


    def counter_integrity_check(self):
        ''' Security measure. Receiver expects to receive a counter value for each command that is higher than the own one.
        This prevents a previously captured stream to be accepted when resent. It matters not how much higher so in case
        a previously failed communication attempt does not lock up the receiver. '''
        cmd_d = self.payload_split
        print(f'counter_integrity_check:: cmd: {self.payload_decrypted}, cmd_d: {cmd_d}')
        try:
            current_counter = self.command_counter[cmd_d[0][:3]]
        except KeyError:
            print(f'counter_integrity_check:: command not found for {cmd_d}')
            self.command_counter_check = False
        counter_rx = int(cmd_d[0][3:])
        print(f'counter_integrity_check:: current_counter: {current_counter}, counter_rx: {counter_rx}')
        self.command_counter_check = current_counter < counter_rx
        if self.command_counter_check:
            self.command_counter[cmd_d[0][:3]] = counter_rx # Possible issue. In Memory, this var is being changed. Upon next succesful pass on another command, it is written to file still. Not goood.

    def parse(self):
        d = self.payload_split
        command = d[0]
        if ABSOLUTE_INDEX_ID in command:
            start = int(d[1])
            end = int(d[2])
            rgb = d[3]
            print(f'ABSOLUTE_INDEX_ID:: {d}, {start}, {end}, {rgb}')
            pixels.set_absolute(start, end, rgb)
            return 1
        if ZONE_INDEX_ID in command:
            zone_id = int(d[1], 16)
            rgb = d[2]
            print(f'ZONE_INDEX_ID:: {d}, {zone_id}, {rgb}')
            pixels.set_zone(zone_id, rgb)
            return 1
        if GRADIENT_ID in command:
            start = int(d[1][:4])
            end = int(d[1][4:])
            rgb = d[2]
            print(f'GRADIENT_ID:: {d}, {start}, {end}, {rgb}')
            return 1
        if TIME_SYNC_ID in command:
            time_stamp = d[1]
            clock.clock_sync(time_stamp)
            return 1
        if BRIGHTNESS_ID in command:
            rgb = d[1]
            pixels.set_brightness(rgb)
            print(f'BRIGHTNESS_ID:: {rgb}')
            return 1
        if DAYLIGHT_ID in command:
            rgb = d[1]
            pixels.set_daylight(rgb)
            print(f'DAYLIGHT_ID:: {rgb}')
            return 1
        if CUSTOM_ID in command:
            mes = d[1]
            pwm = d[2]
            clock.custom_write(mes, pwm)
            print(f'CUSTOM_ID:: mes: {mes}, pwm: {pwm}')
            return 1
        if TEST_ID in command:
            print(f'TEST_ID::  d: {d}')
            return 1
        if ALARM_ID in command:
            abs_or_rel = d[1]
            sev = d[2]
            time_length = d[3]
            #print(f'ALARM_ID:: d: {d}, abs_or_rel: {abs_or_rel}, sev: {sev}, time_lenght: {time_length}')
            if abs_or_rel == 'a':
                alarm.set_alarm(severity=sev, abs_time=time_length)
            if abs_or_rel == 'r':
                alarm.set_alarm(severity=sev, rel_time=time_length)
            print(f'ALARM_ID:: abs_or_rel: {abs_or_rel}, sev: {sev}, time_lenght: {time_length}')
            return  1
        return 0



    def process(self, MAC_address, payload):
        
        self.MAC_whitelist_check(MAC_address) # Checking MAC address against white list.
        if not self.MAC_check: 
            self.error_handler('MAC_WHITELIST', (MAC_address, payload))
            return 0
        self.payload_decrypted = self.decrypt(payload) # Decrypt, if MAC is ok.
        self.payload_split = self.payload_decrypted.split(':')
        self.check_crc() # Checking CRC. If decryption went wrong it should be caught here.
        if not self.CRC_check:
            self.error_handler('CRC', (MAC_address))
            return 0
        self.counter_integrity_check() # Checking received cmd counter against own counter. Rx should be higher than own.
        if not self.command_counter_check:
            self.error_handler('COMMAND_COUNTER', (MAC_address))
            return 0
        if not self.parse():
            self.error_handler('NOT_A_COMMAND', (MAC_address))
            return 0
        led_err.duty_u16(int(0))
        led_ok.duty_u16(int(65535))
        return 1

BT = BT_processor()

rx_data = bytes()
while True:
    while uart.any() > 0:
        if len(payload_list) and data_change:
            data_change = False
            BT.process(central_address, payload_list[-1])

        in_data = uart.read(1)
        rx_data += in_data

        if connect_syntax in rx_data and not is_connected:
            led_err.duty_u16(int(65535))
            led_ok.duty_u16(int(10000))
            rx_data = bytes()
            is_connected = True
            is_MAC = True
            
        if is_connected and is_MAC:
            if len(rx_data) == 12:
                led_err.duty_u16(int(60000))
                led_ok.duty_u16(int(25000))
                is_MAC = False
                is_data = True
                central_address = rx_data
                print(f'address: {central_address}')
                rx_data = bytes()
        if is_connected and is_data:
            if disconnect_syntax in rx_data:
                led_err.duty_u16(int(5000))
                led_ok.duty_u16(int(50000))
                is_data = False
                is_MAC = True
                is_connected = False
                payload = rx_data[:-len(disconnect_syntax)]
                print(f'payload raw: {payload}')
                payload_list.append(payload)
                rx_data = bytes()
        if not is_connected and is_MAC:
            if len(rx_data) == 12:
                led_err.duty_u16(int(50000))
                led_ok.duty_u16(int(5000))                
                is_MAC = False
                print(f'Disconnected from address: {central_address}')
                rx_data = bytes()
                data_change = True
                #print(f'wholeframe: {wholeframe}')
                
            
