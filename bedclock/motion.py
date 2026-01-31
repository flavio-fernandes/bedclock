#!/usr/bin/env python3

import board
import busio
from adafruit_apds9960.apds9960 import APDS9960
from adafruit_apds9960 import colorutility
from datetime import datetime
import dill
import multiprocessing
import signal
from six.moves import queue
import sys
import time

from bedclock import const
from bedclock import events
from bedclock import log

CMDQ_SIZE = 5
_state = None


class State(object):
    def __init__(self, queueEventFun):
        self.queueEventFun = queueEventFun  # queue for output events to main.py
        self.cmdq = multiprocessing.Queue(CMDQ_SIZE)  # queue for input commands
        self.apds = None
        self.luxAboveWatermark = True
        self.luxLastPeriodicReport = datetime.now()
        self.forceNextLuxEvent = True
        # fudge an initial lux value, before real read takes place
        self.currLux = const.motion_luxMaxValue
        self.lastLuxReported = -1
        self.currRawProximity = 999
        self.currProximity = 0
        self.currProximityDampenTimestamp = datetime.now()
        # enabled via main's MotionProcess
        self.luxNotifyEnabled = False
        self.proximityNotifyEnabled = False


# =============================================================================


def ms_sleep(value):
    time.sleep(value / 1000.0)


def on_off_str(boolValue):
    return {True: "on"}.get(boolValue, "off")


# =============================================================================


def do_init(queueEventFun=None):
    global _state
    _state = State(queueEventFun)
    # logger.debug("init called")


# =============================================================================


def _notifyEvent(event):
    global _state
    if _state.queueEventFun:
        logger.debug("generating event: {}".format(event.name))
        _state.queueEventFun(event)


# =============================================================================


def init_apds():
    global _state

    i2c = busio.I2C(board.SCL, board.SDA)
    apds = APDS9960(i2c)
    apds.enable_color = True
    apds.enable_proximity = True

    _state.apds = apds
    logger.info("motion sensor initialized")


# =============================================================================


def do_iterate():
    global _state

    try:
        # Note: since we need to busy poll the motion sensor, we do not
        #       block on input queue. We will microsleep later on
        cmdDill = _state.cmdq.get_nowait()
        cmdFun, params = dill.loads(cmdDill)
        cmdFun(*params)
        logger.debug("executed a lambda command with params %s", params)
        # call iteration done for now, since we did some work if we made
        # it here
        return
    except queue.Empty:
        pass
    except (KeyboardInterrupt, SystemExit):
        pass

    ms_sleep(321)

    if _state.apds is None:
        init_apds()
        return

    do_iterate_light()
    do_iterate_proximity()


# =============================================================================


def do_iterate_light():
    global _state

    if not _state.apds.color_data_ready:
        return

    # get the data and print the different channels
    currLux = _state.currLux
    r, g, b, _c = _state.apds.color_data
    newLux = colorutility.calculate_lux(r, g, b)

    _state.currLux = max(0, int(newLux))
    now = datetime.now()
    tdelta = now - _state.luxLastPeriodicReport

    # Reasons why lux should be reported:
    # 1) explicitly asked to do so
    # 2) predetermined report interval
    # 3) high/low watermark reached
    # 4) big delta
    sendLuxEvent = False
    if _state.forceNextLuxEvent:
        _state.forceNextLuxEvent = False
        sendLuxEvent = True
    elif int(tdelta.total_seconds()) > const.motion_luxReportPeriodInSeconds:
        sendLuxEvent = True
    elif (
        _state.currLux >= const.motion_luxHighWatermark and not _state.luxAboveWatermark
    ):
        _state.luxAboveWatermark = True
        sendLuxEvent = True
    elif _state.currLux <= const.motion_luxLowWatermark and _state.luxAboveWatermark:
        _state.luxAboveWatermark = False
        sendLuxEvent = True
    elif abs(_state.lastLuxReported - _state.currLux) >= const.motion_luxDeltaThreshold:
        sendLuxEvent = True

    if not sendLuxEvent:
        return

    logger.debug("lux update from {} to {}".format(currLux, _state.currLux))

    # create lux event and send it to main
    _state.luxLastPeriodicReport = now
    _state.lastLuxReported = _state.currLux
    if _state.luxNotifyEnabled:
        event = events.MotionLux(_state.currLux)
        _notifyEvent(event)


# =============================================================================


def do_iterate_proximity():
    global _state

    # dampen how often we look at proximity based on the last time
    # the proximity got updated
    now = datetime.now()
    tdelta = now - _state.currProximityDampenTimestamp
    if tdelta.total_seconds() < const.motion_proximityDampenInSeconds:
        return

    oldProximity = _state.currProximity
    newProximity = _state.apds.proximity
    _state.currRawProximity = newProximity

    # if proximity is less than min threshold, set it to 0
    if newProximity < const.motion_proximityMinThreshold:
        newProximity = 0
    if abs(newProximity - _state.currProximity) <= 2:
        # too small of a change... filter it out, unless this is going to 0
        if _state.currProximity == newProximity or newProximity != 0:
            return

    logger.debug(
        "proximity update: from {} to {} (raw {})".format(
            _state.currProximity, newProximity, _state.currRawProximity
        )
    )

    _state.currProximity = newProximity
    _state.currProximityDampenTimestamp = now

    # create proximity event and send it to main
    if _state.proximityNotifyEnabled:
        event = events.MotionProximity(_state.currProximity)
        _notifyEvent(event)
        # Also send a simple motion event for those who just want to know
        # that it happened. When old proximity is 0 it means that no
        # objects were previously detected and that is when we send this
        # event
        if oldProximity == 0 and newProximity > 2:
            event = events.MotionDetected()
            _notifyEvent(event)


# =============================================================================


def _enqueue_cmd(l):
    global _state
    lDill = dill.dumps(l)
    try:
        _state.cmdq.put_nowait(lDill)
    except queue.Full:
        logger.error("command queue is full: cannot add")
        return False
    return True


# called from outside this module
def do_lux_report():
    logger.debug("queuing lux_report request")
    params = []
    return _enqueue_cmd((_do_lux_report, params))


def _do_lux_report():
    global _state
    _state.forceNextLuxEvent = True
    logger.debug("_do_lux_report set state.forceNextLuxEvent")


# called from outside this module
def do_lux_notify_on():
    return _do_lux_notify_onoff(True)


# called from outside this module
def do_lux_notify_off():
    return _do_lux_notify_onoff(False)


# called from outside this module
def do_motion_notify_on():
    return _do_motion_notify_onoff(True)


# called from outside this module
def do_motion_notify_off():
    return _do_motion_notify_onoff(False)


def _do_lux_notify_onoff(newValue):
    return _do_common_notify_onoff(_do_handle_notify_admin_lux, "lux", newValue)


def _do_motion_notify_onoff(newValue):
    return _do_common_notify_onoff(
        _do_handle_notify_admin_proximity, "motion", newValue
    )


def _do_common_notify_onoff(handle_notify_admin_fun, funName, newValue):
    logger.debug("queuing {}_notify_{}".format(funName, on_off_str(newValue)))
    params = [newValue]
    return _enqueue_cmd((handle_notify_admin_fun, params))


def _do_handle_notify_admin_proximity(newValue):
    global _state
    logger.debug("notify motion is now {}".format(on_off_str(newValue)))
    _state.proximityNotifyEnabled = newValue


def _do_handle_notify_admin_lux(newValue):
    global _state
    logger.debug("notify lux is now {}".format(on_off_str(newValue)))
    _state.luxNotifyEnabled = newValue


# =============================================================================


def _signal_handler(signal, frame):
    global stop_trigger
    logger.info("process terminated")
    stop_trigger = True
    sys.exit(0)


# =============================================================================


# globals
stop_trigger = False
logger = log.getLogger()
if __name__ == "__main__":
    log.initLogger()
    do_init(None)
    signal.signal(signal.SIGINT, _signal_handler)
    do_lux_notify_on()
    do_motion_notify_on()
    while not stop_trigger:
        do_iterate()
