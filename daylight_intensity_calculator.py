#!/usr/bin/python3
import math
import sys
from datetime import datetime
import logging
import json
import array
import ast
import os

SCRIPT_NAME, _ = os.path.splitext(os.path.basename(__file__))

SUN_TIMES_FILE = "/home/pi/bluetooth/data/sun_data_table.csv"

PWM_MIN     = 0x1000
PWM_MAX     = 0x7fff
PWM_MID     = 0x1000



"""
Return in time format 'Hh:Mm'.
"""
def get_hour_now() -> str:
    now = datetime.now()
    return now.strftime("%H:%M")

"""
Return day count from start of year (0-365).
"""
def get_day_of_year() -> int:
    return int(datetime.now().strftime('%j'))

"""
Accept timestamp in format 'Hh:Mm' and returns minute count since midnight (0-1440).
"""
def get_mins_from_midnight(time_stamp: str) -> int:
    if isinstance(time_stamp, str) and len(time_stamp) == 5 and time_stamp[2] == ':':
        hours, minutes = time_stamp.split(':')
        total_minutes = (int(hours) * 60) + int(minutes)
        return total_minutes
    else:
        sr_fc = f"{SCRIPT_NAME}: get_mins_from_midnight:"
        print(f"{sr_fc} No valid time stamp provided. Must be 'str' in format %H:%M, not '{time_stamp}'.")
        sys.exit(1)
    
"""
Accepts day count and returns both sun rise and sun set times from lookup table.
"""
def get_sun_times(day_nr: int) -> tuple[str, str]:
    if isinstance(day_nr, int) and day_nr >= 0 and day_nr < 365:
        try:
            date_file = open(SUN_TIMES_FILE, 'r')
        except FileNotFoundError as e:
            sr_fc = f"{SCRIPT_NAME}: get_sun_times:"
            print(f"{sr_fc} Could not find date file for sun set/rise data '{SUN_TIMES_FILE}'.")
            sys.exit(1)
        time_data = date_file.readlines()[day_nr].rstrip()
        time_data = time_data.split(',')
        sun_rise = (time_data[3][:-3]) # Cropping off seconds.
        sun_set  = (time_data[4][:-3])
        return (sun_rise, sun_set) 
    else:
        sr_fc = f"{SCRIPT_NAME}: get_sun_times:"
        print(f"{sr_fc} No valid day number provided. Must be 'int' between 0 and 366, not '{day_nr}'.")
        sys.exit(1)


"""
Calculate PWM value (between PWM_MIN and PWM_MAX) based on current time ,
sun_rise and sun_set (in minutes past midnight).
"""

def get_pwm_value(now: int, sunrise: int, sunset: int) -> int:
    x = now / 1440
    # Adjusted mean and standard deviation for the normalized range
    mu_adjusted = 0.5
    sigma_adjusted = 60 / (sunset - sunrise)
    # Calculate the PDF of the normal distribution
    br1 = (1 / (sigma_adjusted * math.sqrt(2 * math.pi))) * math.exp(
        -((x - mu_adjusted) ** 2) / (2 * sigma_adjusted ** 2)
    )
    br2 = (1 + math.sin(math.pi * x)) / 2

    br4 = br1 / (math.sqrt(1 + br1**2))
    value = br4 * br2
    value = int(PWM_MIN + ((PWM_MAX - PWM_MIN) * value))
    return value


def get_intensity() -> int:
    rise_and_set_tup = get_sun_times(get_day_of_year())
    now = get_hour_now()
    sun_rise = get_mins_from_midnight(rise_and_set_tup[0])
    sun_set  = get_mins_from_midnight(rise_and_set_tup[1])
    now_mn = get_mins_from_midnight(now)
    pwm_value = get_pwm_value(now_mn, sun_rise, sun_set)
    return pwm_value


def main() -> None:
    print(get_intensity())

if __name__ == "__main__":
    main()
    sys.exit(0)



