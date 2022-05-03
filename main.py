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
        self.arr = array.array("I", [0 for _ in range(NUM_LEDS)])
        self.arr_opened = self.arr[:]
        # LED zone assignment.
        self.z_00 = [i for i in range(3, 7)] # AUX UT
        self.z_01 = [i for i in range(7, 23)] # AUX T
        self.z_02 = [i for i in range(23, 31)] # AUX L
        self.z_ff = [i for i in range(32, 46+1)] # JM_SPOT
        self.z_all = self.z_00 + self.z_01 + self.z_02 + self.z_ff
        self.sparkel_level = None
        self.sparkel_enable = True
        self.global_brightness = (1, 1, 1)
        self.daylight_factor = (1, 1, 1)
        
        
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
        rgb_list = []
        if isinstance(data, (int, str)):
            s = ('000000' + str(data)[2:])[-6:] # Ensuring string lenght = 6.
            
            rgb = (int(s[2]+s[3], 16), int(s[0]+s[1], 16), int(s[4]+s[5], 16))
            print(f'rgb_reformatter::: data: {data}, type: {type(data)}, s: {s}, rgb: {rgb}')
            return rgb

        if isinstance(data, (list, tuple)):
            for d in data:
                assert isinstance(d, int)
                s = ('000000' + str(hex(d)))[-6:] # Ensuring string lenght = 6.
                rgb = (int(s[2]+s[3], 16), int(s[0]+s[1], 16), int(s[4]+s[5], 16))
                rgb_list.append(rgb)
            return rgb_list
        print(f'rgb_reformatter:: data: {data}, type: {type(data)}')
        return -1
                      
    def validate_format(self, data):
        print(f'validate_format:: data: {data}, type: {type(data)}')
        if isinstance(data, str):
            print(f'data {data}')
            assert len(data) == 6
            rgb = self.rgb_reformatter(data)
            assert rgb != -1
            return rgb
        if isinstance(data, (list, tuple)):
            assert len(data) == 3
            return data
        assert True == False
            
        
    def output_to_chain(self, data):
        sm.put(data, 8)
        
    
    def rgb_scaling(self, scale_factor, s, e):
        print(f'rgbscaling scalefactor {scale_factor}')
        assert len(scale_factor) == 3
        assert scale_factor != -1
        for b in scale_factor:
            assert b >= 0 
        for i in range(s, e):
            #self.arr[i] = int(self.arr[i] * brightness)
            #self.arr_opened[i] = int(self.arr_opened[i] * scale_factor)
            rgb = self.rgb_reformatter(self.arr[i])
            rgb_new = list(map(lambda x, y: min((int(x * y), 255)), rgb, scale_factor))
            value_new = self.rgb_formatter(rgb_new)            
            #self.arr[i] = value_new
        self.output_to_chain(value_new)


    def set_brightness(self, brightness=(1,1,1), s=None, e=None):
        if s == None:
            s = 0
            e = (NUM_LEDS-1)
        elif e == None:
                e = (NUM_LEDS-1)
                
        self.global_brightness = self.validate_format(brightness)
        print(f'set_brightness:: global_brightness: {self.global_brightness}, brightness: {brightness}, ')
        self.rgb_scaling(self.global_brightness, s=s, e=e)
        
    def set_daylight(self, brightness=(1,1,1), s=None, e=None):
        if s == None:
            s = 0
            e = (NUM_LEDS-1)
        elif e == None:
                e = (NUM_LEDS-1)
        self.rgb_scaling(brightness, s=s, e=e)        
                         
        
    def set_zones(self, rgb, zones=('all')):    #(255<<16) + (255<<8) + 255
        self.arr[2] = self.rgb_formatter((255, 255, 255))
        self.arr[1] = self.rgb_formatter((10, 7, 4))
        self.arr[0] = self.rgb_formatter((10, 7, 4))
        print(f'zones: {zones}')
        
        if 'all' in zones:
            print(f'all zones: {rgb}')
            for i in self.z_all:
                self.arr[i] = self.rgb_formatter(rgb)
        if 'z_00' in zones:
            print(f' z_00: {rgb}')
            for i in self.z_00:
                self.arr[i] = self.rgb_formatter(rgb)
        if 'z_01' in zones:
            print(f' z1: {rgb}')
            for i in self.z_01:
                self.arr[i] = self.rgb_formatter(rgb)
        if 'z_02' in zones:
            print(f' z2: {rgb}')
            for i in self.z_02:
                self.arr[i] = self.rgb_formatter(rgb)
        if 'z_ff' in zones:
            print(f' z_ff: {rgb}')
            for i in self.z_ff:
                self.arr[i] = self.rgb_formatter(rgb)
            
            
        rand_vec = ((255, 220, 20), (180, 200, 40), (255, 60, 180), (255, 220, 240))
        n = len(rand_vec)
        self.arr_opened = self.arr[:]
        self.arr_opened[11] = self.rgb_formatter(rand_vec[random.randrange(n)])
        self.arr_opened[12] = self.rgb_formatter(rand_vec[random.randrange(n)])
        self.arr_opened[13] = self.rgb_formatter(rand_vec[random.randrange(n)])
        self.output_to_chain(self.arr)
        
                   
    def gradient_former(self, s=0, e=8, rgb=(0,80,255)):
        '''Implementing a gradient on a subset of the LED chain, defined by start and end as well as start RGB value.'''
        assert len(rgb) == 3
        start_value = rgb
        end_value = list(map(lambda i: i ^ 0xFF , rgb)) # Inverting bits.
        led_distance = abs(e-s)
        rgb_distance = list(map(lambda x, y: x - y, start_value, end_value)) # Distance vector
        for i in range(led_distance):
            new_rgb = list(map(lambda x, y, z:  int(x -(i*z/led_distance)), start_value, end_value, rgb_distance)) # start - ((brightness*distance)/total_distance)
            self.arr[i+s] = self.rgb_formatter(new_rgb)
        self.output_to_chain(self.arr)
        
    def drawer_closed(self):
        self.output_to_chain(self.arr)
    
    def drawer_opened(self):
        self.arr_opened = self.arr[:]
        self.arr_opened[11] = self.rgb_formatter((random.randrange(85)*2, random.randrange(85)*2, random.randrange(85)*3))
        self.arr_opened[12] = self.rgb_formatter((random.randrange(85)*2, random.randrange(85)*3, random.randrange(85)*2))
        self.arr_opened[13] = self.rgb_formatter((random.randrange(85)*3, random.randrange(85)*2, random.randrange(85)*2))    
        self.output_to_chain(self.arr_opened)
        
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
pixels.set_zones(rgb=(100,100,100), zones='all')
#pixels.gradient_former(s=0, e=40)
#pixels.set_brightness(brightness=(5, 0.6, 5), s=0, e=8)
#pixels.set_brightness(brightness=(5, 0.6, 0.1), s=10, e=40)
#pixels.set_brightness(brightness=(0.1, 0.6, 5), s=38, e=45)
#pixels.set_brightness(brightness=(0.8, 4, 0.4), s=45, e=47)
#pixels.set_zones(rgb=(200,255,50), zones='z_ff')

pixels.sparkel()


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

ABSOLUTE_INDEX_ID = 'AIX000'
ZONE_INDEX_ID = 'ZIX000'
GRADIENT_ID = 'GRA000'
TIME_SYNC_ID = 'TSY000'
BRIGHTNESS_ID = 'BRI000'
DAYLIGHT_ID = 'DAL000'

def bt_data_processing(payload):
    d = str(payload)[2:-1].split(':')
    print(f'processing payload: {payload}, d: {d}')
    command = d[0]
    data = d[1]

    if ABSOLUTE_INDEX_ID in command:
        pass
    if ZONE_INDEX_ID in command:
        pass
    if GRADIENT_ID in command:
        pass
    if TIME_SYNC_ID in command:
        pass
    if BRIGHTNESS_ID in command:
        hexval = pixels.rgb_reformatter(data)
        print(f'bt_data_processing:: hexval: {hexval}')
        floatval = list(map(lambda x: ((x)/128), hexval))
        print(f'bt_data_processing:: hexval: {hexval}, floatval: {floatval}')
        pixels.set_brightness((data))
    if DAYLIGHT_ID in command:
        pass
    

    
    
    
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
                
            
        
            
