#!/usr/bin/env python3

# options related to mqtt
mqtt_broker_ip = "192.168.10.238"
mqtt_enabled = True
mqtt_topic_prefix = "bedclock"
mqtt_topic_pub_light = "light"
mqtt_topic_pub_motion = "motion"
mqtt_topics_pub = {t: "/{}/{}".format(mqtt_topic_prefix, t) for t in [
        mqtt_topic_pub_light, mqtt_topic_pub_motion]}
mqtt_topic_sub_stay = "stay"
mqtt_topic_sub_temperature = "temperature_outside"
mqtt_topics_sub = {t: "/{}/{}".format(p, t) for p, t in [
    (mqtt_topic_prefix, mqtt_topic_sub_stay),
    ("sensor", mqtt_topic_sub_temperature),
]}
mqtt_value_enable = set(["on", "true", "enable", "enabled", "1", "up", "yes", "yeah", "yup", "y"])

# options passed into rgb matrix
# ['regular', 'adafruit-hat', 'adafruit-hat-pwm']
scr_led_gpio_mapping = 'adafruit-hat-pwm'
scr_fonts_dir = "/home/pi/rpi-rgb-led-matrix/fonts"
scr_led_rows = 64
scr_led_cols = 64
scr_led_chain = 1
scr_led_parallel = 1
scr_row_address_type = 0
scr_led_multiplexing = 0
scr_led_pwm_bits = 11
#scr_led_brightness =
scr_led_pwm_lsb_nanoseconds = 130
scr_led_rgb_sequence = "RBG"
scr_led_show_refresh = False
scr_led_slowdown_gpio = None
scr_led_no_hardware_pulse = False
scr_pixel_mapper_config = "Rotate:90"

# other screen related values
scr_brightnessOff = 0
scr_brightnessMinValue = 8
scr_brightnessMaxValue = 98
scr_wakeupTimeoutInSeconds = 12
scr_stayOnInDarkRoomDefault = False

# motion
motion_proximityMinThreshold = 6
motion_proximityDampenInSeconds = 3
motion_luxReportPeriodInSeconds = 601
motion_luxLowWatermark = 6
motion_luxHighWatermark = 19
motion_luxDeltaThreshold = 196

# lux can go to 7k, but anything beyond 2k is max bright
motion_luxMinValue = 0
motion_luxMaxValue = 2123
motion_luxDarkRoomThreshold = motion_luxLowWatermark
