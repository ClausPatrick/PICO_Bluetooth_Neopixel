# PICO_Bluetooth_Neopixel
RP2020 PICO as BLE periphery to control WS2812B Neoplixels



-IO:

Pin0 in (sm) WS2818 chain
Pin1 out (draw_sw) sensor switch, frontside
Pin5 out/pwm (led_ok) GREEN led, frontside
Pin6 out/pwm (led_err) RED led, frontside
Pin12 UART_TX to HM18 UART_RX
Pin13 UART_RX to HM18 UART_TX
Pin16 out/pwm CD4049 pwm_pin
Pin17 out CD4049 clock_pin
Pin18 out CD4049 data_pin
Pin19 out CD4049 strobe_pin

Pin25 (led_onboard) Onboard GREEN led


Originally intended to be a dumb pass-through of data from the central (RaspberryPi 4B) to control light chain comprissed of RGB chips however after emperical testing it seems that there is a limited amout of bytes that can be transmitted per session within the GATT protocols so a set of commands are devised to display certain patterns of colours in various brightness levels corresponding to daylight brightness. 
The RP2020 also controls a set of 4 seven-seg displays for time. The display is controlled via 4 CD4094 that receive data and is interfaced via the CD4094_class.
The aformentioned set of commands allows for time synchronisation with a precision limited by the bluetoot transfer delay (experienced to be less than 30 seconds).



class bt_dict_processor

Absence of some micropython libs some wrangling is done to safe the nested dicts as a string and then do the reverse. The store_data() function should be invoked upon succesfull processing of the received BT session.
Upon reset registers are updated from flash when fetch_data() is invoked. Outside, when alarm_list and command_counter are changed, the function store_data() will commit this into flash.

This way all data that needs storing is handled here instead of spread out. This requires a bt_dict.txt file containing lines containing:
-key for encryption;
-alarm_list;
-hostnames (list of all host names);
Then the following 3 lines are needed for each connecting host:
-hashed MAC address as string;
-hostname as string;
-command counter as dict;
As now the command counter is kept for each connecting host there would be no issue to ensure the command counter security routine for multiple hosts.

bt_dict.txt:
a53[]3\'3%548^#1/3
{21600: {severity: 0, duration: 40, persistence: 1, abs_time: 0600}}
host1, host2, host3
host1
b's\xb0z_\x17\xc7\r\xe2\xd2\x7f\xfds\xd8\x04\x01\x88\xc5c\x7f\xee\xb3\xe4\x60C\x10\xa4\xdee\xe1e\xa4\xb3'
{'AIX': 0, 'ALM': 0, 'DAL': 0, 'TSY': 0, 'CDP': 0, 'TST': 0, 'ZIX': 0, 'BRI': 0, 'ALD': 0, 'GRA': 0}
host2
b'\xedV\xcc\x13g\xc6\xd5\xb9&\x0e>\x9d\xb6\x42\xcag\xb6\xf2\x85xG \xe6l\xa5\xb5\x1bV\xecH#\xcb'
{'AIX': 0, 'ALM': 0, 'DAL': 0, 'TSY': 0, 'CDP': 0, 'TST': 0, 'ZIX': 0, 'BRI': 0, 'ALD': 0, 'GRA': 0}
host3
b'*t2/\xf2Y\xa4x\x1a\x3f\xb4\xd9\x1d\xbe\x92.\xfc\xc2\x9b\xe1n\xcd\xd0\x1c=^\x00P8\x82\\\x89'
{'AIX': 0, 'ALM': 0, 'DAL': 0, 'TSY': 0, 'CDP': 0, 'TST': 0, 'ZIX': 0, 'BRI': 0, 'ALD': 0, 'GRA': 0}



PIO_state_machine

Interfaces with WS2812's via PIO_state_machine.put(). LEDs are RGB in format 0xRRGGBB (int) where R, G, B are 0~255 (0~0xFF).


class Clock

Processes BT data pertaining to time sync (clock_sync()) to display (display_current_time())  it and scheduling, excuting and deleting alarms. From bt_dict_processor alarm_list is required. Each instance of alarm will have its time, severity (chooses the style in notify()) duration (seconds) and whether it is persistance. A persistant instance will not be deleted once its time was matched and the notify() ran.


class LED_admin

Organises all LED RGB data in an array. The data in said array is calculated from user data, brightness- and daylight factor. There are various way to compose a colour scheme. Zone and Absolute are static in that the same value is copied into the corresponding LEDs. The gradient function is dynamic giving each LED a slice of the gradient.
During the alarm notification events and the sparkel() routine will highjack the array temporarly and upon completion they will be set back.
The sparkel() function pulses random LED giving an aestatically interesting effect.
An external sensor connected to furniture will allow some designated LEDs to light up providing extra light. This is handeld by an interupt draw_routine().


class BT_processor

Once BT session is closed, both MAC and DATA are processed here. If 1 is returned all security measures have passed, the command is handled and all registers are updated. These security measures are discussed seperately. The process() function is the orchestrator that chains the different methods together. Following security clearance the message's command is parsed and various actions are taken.

The programs loops around UART receiption. String matching on the inbound UART data will progress through different phases to retrieve the MAC address and the payload. 





![20230130_112420](https://user-images.githubusercontent.com/44665589/215466223-b65e01a6-42e7-4f4b-a1b4-130c81ee8075.jpg)




https://user-images.githubusercontent.com/44665589/215466243-dce9bb75-1a24-40f2-bdfb-70dcbc607201.mp4



