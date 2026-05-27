import machine
from time import sleep
import random
import utime
import time
import _thread


#led_onboard = machine.Pin(25, machine.Pin.OUT)

cd_symbols = {'0': '00011000',
              '1': '11011110',
              '2': '00110100',
              '3': '10010100',
              '4': '11010010',
              '5': '10010001',
              '6': '00010001',
              '7': '11011100',
              '8': '00010000',
              '9': '10010000',
              'a': '01010000',
              'b': '00010011',
              'c': '00111001',
              'd': '00010110',
              'e': '00110001',
              '-': '11110111',
              'None': '11111111',
              '.': '11101111'}
    
class CD4094():

    
    def __init__(self, clock_pin=17, data_pin=18, strobe_pin=19, pwm_pin=16, pwm_freq=1000, pwm_duty=0xffff):
        self.number_of_ics = 4
        self.cd_clock = machine.Pin(clock_pin, machine.Pin.OUT)
        self.cd_data = machine.Pin(data_pin, machine.Pin.OUT)
        self.cd_strobe = machine.Pin(strobe_pin, machine.Pin.OUT)
        self.cd_pwm = machine.PWM(machine.Pin(pwm_pin))
        self.cd_pwm.freq(pwm_freq)
        self.cd_pwm.duty_u16(pwm_duty)
        self.red = 0
        self.cd_strobe.value(0)
        

    def transmit(self, data=0, red=0, pwm_duty=0xffff):
        '''Translating data {str or int} into str of 0/1 and clock them into CD4094. 4 * 7 seg + d.p accounts for 32 values, + 1 for extra LED (red) for Q_s on last IC'''
        self.red = red
        self.cd_strobe.value(0)
        self.cd_pwm.duty_u16(pwm_duty)
        self.data_formated = '1' * 8 * self.number_of_ics + str(1-self.red) # Works as buffer and is prefilled to clear display in case len(data) < 4.
        for s in str(data):
            #print(f's: {s}')
            if s in cd_symbols:
                if s == '.':
                    data_list = list(self.data_formated)
                    data_list[-5] = '0' # Set decimal point. Str is not mutable so setting it to list first then back to str.
                    self.data_formated = ''.join(data_list)
                else:
                    self.data_formated += cd_symbols[s]
            else:
                self.data_formated += cd_symbols['None']
        self.data_formated = self.data_formated[-(self.number_of_ics*8 + 1):]
        #print(self.data_formated)
        for d in self.data_formated:
            b = int(d)
            self.cd_clock.value(0)
            self.cd_data.value(b)
            self.cd_clock.value(1)
        self.cd_strobe.value(1)
        

def main():        
    #cd = CD4094()
    #cd.transmit(123.4, red=1, pwm_duty = (0xffff//1))
    pass
    


# call main
if __name__ == '__main__':
    main()


