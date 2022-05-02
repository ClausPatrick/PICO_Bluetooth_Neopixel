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
        
    def rgb_formatter(self, data):
        '''Array of 3 RGB data converted to fit Neopixel format (GgRrBb where character-pair is 1 byte size). Error return -1
        if shit goes sideways.
        '''
        if len(data) == 3:
            return sum([i<<j for i, j in zip(data, (8, 16, 0))])
        else:
            return -1
        
    def output_to_chain(self, data):
        sm.put(data, 8)
        
    def set_brightness(self, brightness=1):
        assert brightness >= 0 and brightness <= 1
        for i in range(self.NUM_LEDS):
            self.arr[i] = int(self.arr[i] * brightness)
            self.arr_opened[i] = int(self.arr_opened[i] * brightness)
            
        
        
    def set_zones(self, z0=(0,0,0), z1=(0,0,0), z2=(0,0,0), z3=(0,0,0), all_zones=None):    #(255<<16) + (255<<8) + 255
        self.arr[2] = self.rgb_formatter((255, 255, 255))
        self.arr[1] = self.rgb_formatter((10, 7, 4))
        self.arr[0] = self.rgb_formatter((10, 7, 4))

        for i in self.z_00:
            if all_zones == None:
                self.arr[i] = self.rgb_formatter(z0)
            else:
                self.arr[i] = self.rgb_formatter(all_zones)
            
        for i in self.z_01:
            if all_zones == None:
                self.arr[i] = self.rgb_formatter(z1)
            else:
                self.arr[i] = self.rgb_formatter(all_zones)

        for i in self.z_02:
            if all_zones == None:
                self.arr[i] = self.rgb_formatter(z2)
            else:
                self.arr[i] = self.rgb_formatter(all_zones)

        for i in self.z_ff:
            if all_zones == None:
                self.arr[i] = self.rgb_formatter(z3)
            else:
                self.arr[i] = self.rgb_formatter(all_zones)

        rand_vec = ((255, 180, 20), (180, 255, 20), (255, 20, 180))
        self.arr_opened = self.arr[:]
        self.arr_opened[11] = self.rgb_formatter(rand_vec[random.randrange(3)])
        self.arr_opened[12] = self.rgb_formatter(rand_vec[random.randrange(3)])
        self.arr_opened[13] = self.rgb_formatter(rand_vec[random.randrange(3)])
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
    


pixels = LED_admin()
pixels.set_zones(all_zones=(140,0,60))
#pixels.gradient_former(s=0, e=40)
#pixels.set_brightness(0.2)

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


def bt_data_processing(data):
    print(f'processing {data}')
    
    
    
def sparkel_func(timer):
    #print(random.randrange(NUM_LEDS))
    freq_list = (2.4, 2.2, 2, 1.  , 0.5 , 0.33, 1.25, 1.117, 1.64)
    if draw_sw.value() == 0:
        arr_copy = pixels.arr[:]
        bling = (255, 220, 160)
        rand_index = random.randrange(NUM_LEDS)
        for i in range(24):
            ii = int(i/4 + 1)
            rand_value = (bling[random.randrange(3)]//ii, bling[random.randrange(3)]//ii,bling[random.randrange(3)]//ii)
            rand_index_mult = random.randrange(NUM_LEDS)
            #arr_copy[rand_index_mult] = rgb_formatter(rand_value)
            arr_copy[rand_index] = pixels.rgb_formatter(rand_value)
            arr_copy[0] = pixels.rgb_formatter(rand_value)
            sm.put(arr_copy, 8)
            utime.sleep_ms(6)
        sm.put(pixels.arr, 8)
        new_freq = freq_list[random.randrange(len(freq_list))]
        sparkel_timer.init(freq=new_freq, mode=Timer.PERIODIC, callback=sparkel_func) 
    
    

sparkel_timer = Timer()
sparkel_timer.init(freq=2, mode=Timer.PERIODIC, callback=sparkel_func)    
    
    
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
                print(f'payload: {payload}')
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
                
            
        
            
