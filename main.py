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
#from machine import Pin, Timer, I2C

   
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

NUM_LEDS = 57

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
        
    def time_formatter(self, ticks):
        '''Var ticks (0 to 24*60) to timeformat HhMm. '''        
        assert ticks <= (24 * 60)
        h = '00' + str((ticks) // 60)
        m = '00' + str((ticks) % 60)
        t = h[-2:] + m[-2:]
        return t
    
    
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
        print(f'time_to_ticks:: data: {data}, {type(data)}, c_sync: {c_sync}, f_sync: {f_sync}, ticks_new: {ticks_new}')
        return (ticks_new, f_sync)
    
    def clock_sync(self, data):
        print(f'clock_sync:: data: {data}')
        assert len(data) == 6 and isinstance(data, str)
        ticks, tick_quarter = self.time_to_ticks(data)
        print(f'clock_sync:: data:{data}, {type(data)}, ticks: {ticks}, tick_quarter: {tick_quarter}')
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
        
        
    
clock = Clock()
clock.ticker()

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


pixels = LED_admin()
pixels.sparkel()
pixels.set_zone(zone_nr=0, rgb_str=(255, 0, 255))
utime.sleep_ms(5)
pixels.set_zone(zone_nr=1, rgb_str='0000ff')
utime.sleep_ms(5)
pixels.set_zone(zone_nr=2, rgb_str='00ff00')
utime.sleep_ms(5)
pixels.set_zone(zone_nr=3, rgb_str=(255, 0, 0))
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

BT_NAME = "Illuminati"
MSG_OK = "AT"
MSG_GET_ADDRESS = "AT+ADDR?"
MSG_DISCOVER = "AT+DISC?" # requires AT+IMME1 and AT+ROLE1 
MSG_GET_NAME = "AT+NAME?"
MSG_SET_NAME = "AT+NAME" + BT_NAME
MSG_RESTART = "AT+RESET"
MSG_GET_ROLE = "AT+ROLE?"
MSG_GET_UUID = "AT+UUID?"
MSG_SET_ROLE_0 = "AT+ROLE0"
MSG_SET_ROLE_1 = "AT+ROLE1"
MSG_GET_MODE = "AT+MODE?"
MSG_SET_MODE_0 = "AT+MODE0" # Transmission mode
MSG_SET_MODE_1 = "AT+MODE1" # Remote control mode
MSG_SET_MODE_2 = "AT+MODE2" # Limited remote-control mode
MSG_GET_HELP = "AT+HELP?"
MSG_GET_WORKTYPE = "AT+IMME?"
MSG_GET_NOTI = "AT+NOTI?"
MSG_SET_NOTI_0 = "AT+NOTI0"
MSG_SET_NOTI_1 = "AT+NOTI1"
MSG_GET_NOTP = "AT+NOTP?"
MSG_SET_NOTP_0 = "AT+NOTP0"
MSG_SET_NOTP_1 = "AT+NOTP1"
  
    
message = MSG_GET_MODE
uart.write(message.encode('ascii'))

print(f'sent MESSAGE: {message}')
rx_data = bytes()

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


ABSOLUTE_INDEX_ID = 'AIX000' # RGB, Start, Offset
ZONE_INDEX_ID = 'ZIX000' # RGB, Zone_list_lengt, Zones
GRADIENT_ID = 'GRA000' # RGB, Start, Offset
TIME_SYNC_ID = 'TSY000' # 
BRIGHTNESS_ID = 'BRI000' # RGB
DAYLIGHT_ID = 'DAL000' # RGB
CUSTOM_ID = 'CDP000' # RGB, PWM
TEST_ID = 'TST000'
ENCRYPT_ID = 'ENC000'


def decrypt(cmd):
    assert isinstance(cmd, bytes), "Input not Bytes"
    lenght = len(cmd)
    key_lenght = len(key)
    cmd_bytes = cmd
    new = ''
    for i, b in enumerate(cmd_bytes):
        key_index = i % key_lenght
        key_mask = ord(key[key_index]) & 0b00011111
        new += ''.join(chr(b ^ key_mask))
    print(f'decrypt:: clean: {cmd},  new: {new}\n')    
    return new 
    
key = private_key.key

def bt_data_processing(payload):
    if payload == '':
        print(f'bt_data_processing:: Attempt transferring data failed. Communication initiated but payload is void.')
        return 
    print(payload)

    decrypted = decrypt(payload)
    d = decrypted.split(':')
    print(f'processing payload: {decrypted}, d: {d}')
    command = d[0]

    if ABSOLUTE_INDEX_ID in command:
        start = int(d[1])
        end = int(d[2])
        rgb = d[3]
        print(f'ABSOLUTE_INDEX_ID:: {d}, {start}, {end}, {rgb}')
        pixels.set_absolute(start, end, rgb)
    if ZONE_INDEX_ID in command:
        zone_id = int(d[1], 16)
        rgb = d[2]
        print(f'ZONE_INDEX_ID:: {d}, {zone_id}, {rgb}')
        pixels.set_zone(zone_id, rgb)
    if GRADIENT_ID in command:
        start = int(d[1][:4])
        end = int(d[1][4:])
        rgb = d[2]
        print(f'GRADIENT_ID:: {d}, {start}, {end}, {rgb}')
    if TIME_SYNC_ID in command:
        time_stamp = d[1]
        clock.clock_sync(time_stamp)
    if BRIGHTNESS_ID in command:
        rgb = d[1]
        pixels.set_brightness(rgb)
        print(f'BRIGHTNESS_ID:: {rgb}')
    if DAYLIGHT_ID in command:
        rgb = d[1]
        pixels.set_daylight(rgb)
        print(f'DAYLIGHT_ID:: {rgb}')
    if CUSTOM_ID in command:
        mes = d[1]
        pwm = d[2]
        clock.custom_write(mes, pwm)
        print(f'CUSTOM_ID:: mes: {mes}, pwm: {pwm}')
    if TEST_ID in command:
        print(f'TEST_ID::  d: {d}')        
    return 

allowed_central_list = MAC_hash_list.hashlist

while True:
    while uart.any() > 0:
        if len(payload_list) and data_change:
            data_change = False
            #bt_data_processing(payload_list[-1])
            if hashlib.sha256(central_address).digest() in allowed_central_list:
                print(f'Central address verified, {central_address}')
                bt_data_processing(payload_list[-1])
            else:
                print(f'Central address NOT verified. Dropping data.  {hashlib.sha256(central_address).digest()}, {central_address}, {payload_list}')

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
                led_ok.duty_u16(int(5000))
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
                
            
        
            

