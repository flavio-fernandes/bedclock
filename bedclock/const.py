#!/usr/bin/env python3

MOTION = "motion"

topics = ["light", MOTION, "display"]

bedclock_topic = {t: "/bedclock/{}".format(t) for t in topics}

# options passed into rgb matrix
# ['regular', 'adafruit-hat', 'adafruit-hat-pwm']
scr_led_gpio_mapping = 'adafruit-hat'
scr_fonts_dir = "/home/pi/rpi-rgb-led-matrix/fonts"
scr_led_rows = 64
scr_led_cols = 64
scr_led_chain = 1
scr_led_parallel = 1
scr_row_address_type = 0
scr_led_multiplexing = 0
scr_led_pwm_bits = 11
#scr_led_brightness = 98
scr_led_pwm_lsb_nanoseconds = 130
scr_led_rgb_sequence = "RBG"
scr_led_show_refresh = False
scr_led_slowdown_gpio = None
scr_led_no_hardware_pulse = False

# other screen related values
scr_brightnessOff = 0
scr_brightnessMinValue = 34
scr_brightnessMaxValue = 100
scr_wakeupTimeoutInSeconds = 10

# motion
motion_proximityDampenInSeconds = 3
motion_luxChangeThreshold = 250
motion_luxReportPeriodInSeconds = 601

# lux can go to 7k, but anything beyond 2k is max bright
motion_luxMinValue = 0
motion_luxMaxValue = 2110
motion_luxDarkRoomThreshold = 5
