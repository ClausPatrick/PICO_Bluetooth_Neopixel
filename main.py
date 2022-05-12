import array, utime, time
from machine import Pin, Timer, I2C
import rp2
from rp2 import PIO, StateMachine, asm_pio
from time import sleep
import re
import random
#from machine import Pin, Timer, I2C

led_onboard = machine.Pin(25, machine.Pin.OUT)
led_onboard.value(1)

uart = machine.UART(0, 9600, tx=Pin(12), rx=Pin(13), bits=8, parity=None, stop=1)

led_ok = machine.PWM(machine.Pin(5))
led_err = machine.PWM(machine.Pin(6))
draw_sw = machine.Pin(1, machine.Pin.IN, machine.Pin.PULL_UP)
led_ok.freq(1000)
led_err.freq(1000)
led_ok.duty_u16(65535)
led_err.duty_u16(0)

NUM_LEDS = 57
#arr = array.array("I", [0 for _ in range(NUM_LEDS)])
#curve = [int((256 ** (1 - (i/NUM_LEDS)))- 1) for i in range(NUM_LEDS)]

#sideset_init=(PIO.OUT_LOW,) * 2, out_init=rp2.PIO.OUT_HIGH

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

    def rgb_formatter(self, data):
        '''Array of 3 RGB data converted to fit Neopixel format (GgRrBb where character-pair is 1 byte size). Error return -1
        if shit goes sideways.
        '''
        if len(data) == 3:
            return sum([i<<j for i, j in zip(data, (8, 16, 0))])
        else:
            return -1      

    def rgb_reformatter(self, data):
        '''Opposite of rgb_formatter. '''
        if isinstance(data, int):
            s = ('000000' + str(hex(data)[2:]))[-6:] # Ensuring string lenght = 6.  
            #print(f'rgb_reformatter:: isinstance:: {type(data)}, data: {data}, s: {s}')         
        elif isinstance(data, str):
            s = ('000000' + data)[-6:]
            #print(f'rgb_reformatter:: isinstance:: {type(data)}, data: {data}, s: {s}')   
        else:
            #print(f'rgb_reformatter:: data: {data}, type: {type(data)}')
            raise ValueError
        rgb = (int(s[2]+s[3], 16), int(s[0]+s[1], 16), int(s[4]+s[5], 16))
        #print(f'rgb_reformatter:: data: {data}, {hex(data)}, type: {type(data)}, s: {s}, rgb: {rgb}')
        return rgb

    def output_to_chain(self, data):
        sm.put(data, 8)
    
    def rgb_scaling(self):
        for i in range(NUM_LEDS):
            s = ('000000' + str(hex(self.rgb_list[i]))[2:])[-6:]
            #print(f's: {s}, {type(s)}')
            s0 = str(hex(min(int(int(s[0:2], 16) * (self.brightness_list[0] / 127) * (self.daylight_list[0] / 255)), 255)))[2:]
            s1 = str(hex(min(int(int(s[2:4], 16) * (self.brightness_list[1] / 127) * (self.daylight_list[1] / 255)), 255)))[2:]
            s2 = str(hex(min(int(int(s[4:6], 16) * (self.brightness_list[2] / 127) * (self.daylight_list[2] / 255)), 255)))[2:]
            self.arr[i]  = int(('00' + s0)[-2:] + ('00' + s1)[-2:] + ('00' + s2)[-2:], 16)
            #print(f'rgb_scaling:: s: {s}, s0: {s0}, s1: {s1}, s2: {s2}, new: {self.arr[i]}')

    def set_brightness(self, brightness='7f7f7f'):
        self.brightness_factor = brightness
        brightness_reformed = self.rgb_reformatter(brightness)
        assert brightness_reformed != -1
        #print(f'set_brightness:: brightness: {brightness}, brightness_reformed: {brightness_reformed}')
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
            #print(ix, dx)
            a = self.rgb_reformatter(self.arr[ix])
            b = self.rgb_reformatter(self.rgb_list[ix])
            print(f'    arr: {a}, rgb: {b}')

    def insist_int(self, rgb_str):
        if isinstance(rgb_str, int):
            rgb = rgb_str         
        elif isinstance(rgb_str, str):
            rgb = int(rgb_str, 16)
        else:
            #print(f'rgb_reformatter:: data: {data}, type: {type(data)}')
            raise ValueError        
        return rgb

    def set_absolute(self, start=0, end=NUM_LEDS+1, rgb_str='2f1f0f'):
        rgb = self.insist_int(rgb_str)
        for i in range(start, end):
            self.rgb_list[i] = rgb
            #print(f'set_absolute:: {i}, {self.arr[i]}')
        self.rgb_scaling()
        self.output_to_chain(self.arr)

    def set_zone(self, zone_nr=0, rgb_str='2f1f0f'):
        rgb = self.insist_int(rgb_str)
        for z in self.z_list[zone_nr]:
            self.rgb_list[z] = rgb
            #print(f'set_zone:: {zone_nr}-{z}, arr: {self.arr[z]}, rgb_list: {self.rgb_list[z]}')
        self.rgb_scaling()
        self.output_to_chain(self.arr)

    def sparkel(self, f='h', l='h', s='h'):
        new_freq = 2
        freq_list_full = (2.4, 2.2, 2, 1.64, 1.25, 1.117, 1, 0.8, 0.5, 0.33, 0.1)
        freq_list = freq_list_full[:]
        def sparkel_func(timer):
            #print(random.randrange(NUM_LEDS))
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
                    #arr_copy[rand_index_mult] = rgb_formatter(rand_value)
                    arr_copy[rand_index] = self.rgb_formatter(rand_value) # Btw 0 and NUM_LEDS (incl)
                    #arr_copy[0] = pixels.rgb_formatter(rand_value)
                    self.output_to_chain(arr_copy)
                    utime.sleep_ms(rand_time) # Btw 4 and 16 (incl)
                self.output_to_chain(self.arr)
                new_freq = freq_list[random.randrange(len(freq_list))]
                self.sparkel_timer.init(freq=new_freq, mode=Timer.PERIODIC, callback=sparkel_func)
        self.sparkel_timer = Timer()
        self.sparkel_timer.init(freq=2, mode=Timer.PERIODIC, callback=sparkel_func)     


pixels = LED_admin()

pixels.sparkel()
pixels.set_zone(zone_nr=0, rgb_str='00f07f')
pixels.set_zone(zone_nr=1, rgb_str='7f0f7f')
pixels.set_zone(zone_nr=2, rgb_str='f00f7f')
pixels.set_zone(zone_nr=3, rgb_str='077f2f')
pixels.set_brightness('0f0f0f')

drawer_opened = 0


def draw_routine(pin):
    global drawer_opened
    utime.sleep_ms(10)
    if drawer_opened != draw_sw.value():
        drawer_opened = draw_sw.value()
        led_err.duty_u16(int(65535 * draw_sw.value()))
        #led_ok.duty_u16(int(65535 * (1 - draw_sw.value())))
        if draw_sw.value():
            #sm.put(pixels.arr_opened, 8)
            pixels.drawer_opened()
        else: 
            #sm.put(pixels.arr, 8)
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
#connect_syntax = b"OK+Get:0OK+CONN:"
connect_syntax = b"OK+CONN:"
disconnect_syntax = b"OK+LOST:"
inbound = False
payload_list = []
wholeframe = bytes()
led_err.duty_u16(int(0))
led_ok.duty_u16(int(65535))

    
def decode_bt_data(data):
    colour_factor_list = (16, 8, 0)
    data = str(data)[2:-1]
    data = data[:(NUM_LEDS*6)]
    arr = array.array("I", [0 for _ in range(NUM_LEDS)])
    print(f'cropped data: {data}')
    for i, b in enumerate(data):
        led_index = i // 6
        nibb_index = 1 - (i % 2)
        colour_index = (i//2) % 3
        value = int(b, 16) << (nibb_index * 4)
        colour_factor = colour_factor_list[colour_index]
        value_colour = value << colour_factor
        arr[led_index] += value_colour
    print(f'arr: {arr}')
    return arr

ABSOLUTE_INDEX_ID = 'AIX000' # RGB, Start, Offset
ZONE_INDEX_ID = 'ZIX000' # RGB, Zone_list_lengt, Zones
GRADIENT_ID = 'GRA000' # RGB, Start, Offset
TIME_SYNC_ID = 'TSY000' # 
BRIGHTNESS_ID = 'BRI000' # RGB
DAYLIGHT_ID = 'DAL000' # RGB

def bt_data_processing(payload):
    d = str(payload)[2:-1].split(':')
    print(f'processing payload: {payload}, d: {d}')
    command = d[0]

    if ABSOLUTE_INDEX_ID in command:
        start = int(d[1], base=16)
        end = int(d[2], base=16)
        rgb = d[3]
        print(f'ABSOLUTE_INDEX_ID:: {d}, {start}, {end}, {rgb}')
        pixels.set_absolute(start, end, rgb)
    if ZONE_INDEX_ID in command:
        zone_id = int(d[1], base=16)
        rgb = d[2]
        print(f'ZONE_INDEX_ID:: {d}, {zone_id}, {rgb}')
        pixels.set_zone(zone_id, rgb)
    if GRADIENT_ID in command:
        start = int(d[1][:4], base=16)
        end = int(d[1][4:], base=16)
        rgb = d[2]
        print(f'GRADIENT_ID:: {d}, {start}, {end}, {rgb}')
    if TIME_SYNC_ID in command:
        time_stamp = rgb = d[1]
    if BRIGHTNESS_ID in command:
        rgb = d[1]
        pixels.set_brightness(rgb)
        print(f'BRIGHTNESS_ID:: {rgb}')
    if DAYLIGHT_ID in command:
        rgb = d[1]
        print(f'DAYLIGHT_ID:: {rgb}')

    
    
    
while True:
    while uart.any() > 0:
        if len(payload_list) and data_change:
            data_change = False
            bt_data_processing(payload_list[-1])

        in_data = uart.read(1)
        rx_data += in_data
        #wholeframe += in_data

        if connect_syntax in rx_data and not is_connected:
            led_err.duty_u16(int(65535))
            led_ok.duty_u16(int(10000))
            #rx_data = rx_data[-len(connect_syntax):]
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
                
            
        
            

