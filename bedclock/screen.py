#!/usr/bin/env python3

from datetime import datetime
from datetime import timedelta
import dill
import multiprocessing
import signal
from six.moves import queue
import os
import sys

from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions

# need this because exported python path gets lost when invoking sudo
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from bedclock import const  # noqa
from bedclock import events  # noqa
from bedclock import log  # noqa

CMDQ_SIZE = 100
TIMERTICK_UNIT = 0.25  # 250ms (in seconds)
_state = None


class State(object):
    def __init__(self, queueEventFun):
        self.queueEventFun = queueEventFun  # queue for output events
        self.cmdq = multiprocessing.Queue(CMDQ_SIZE)  # queue for input commands
        self.matrix = None
        self.cachedNormalizedLux = const.scr_brightnessMaxValue
        self.cachedProximity = 0
        self.timer_tick_services = []
        self.fonts = []
        timer_tick_data = {
            "black": graphics.Color(0, 0, 0),
            "green": graphics.Color(0, 255, 0),
            "blue": graphics.Color(0, 0, 255),
            "red": graphics.Color(255, 0, 0),
        }
        self.timer_tick_data = timer_tick_data

        # screen brightness behavior state
        self.currentBrightness = const.scr_brightnessMaxValue
        self.wantedBrightness = self.currentBrightness
        self.useLuxToDetermineBrightness = True

        # do not mess with brightness timeout in seconds
        # will attempt to update currentBrightness to match
        # wantedBrightness only if timeout is 0. If this is
        # set to a negative value, that means timeout will
        # never converge to 0
        self.stayOnCurrentBrightnessTimeout = const.scr_wakeupTimeoutInSeconds

        # is room is dark, the knob below dictates wheter screen
        # should go completely blank or not
        self.stayOnInDarkRoom = const.scr_stayOnInDarkRoomDefault


# =============================================================================


def do_init(queueEventFun=None):
    global _state
    _state = State(queueEventFun)

    logger.debug("init called")


# =============================================================================


def _notifyEvent(event):
    global _state
    if _state.queueEventFun:
        logger.debug("generating event: {}".format(event.name))
        _state.queueEventFun(event)


# =============================================================================


def _notifyEventLuxUpdateRequest():
    requester = os.path.split(__file__)[-1]
    requester = requester.split(".py")[0]
    event = events.LuxUpdateRequest(requester)
    _notifyEvent(event)


# =============================================================================


def init_matrix():
    global _state

    options = RGBMatrixOptions()
    options.hardware_mapping = const.scr_led_gpio_mapping
    options.rows = const.scr_led_rows
    options.cols = const.scr_led_cols
    options.chain_length = const.scr_led_chain
    options.parallel = const.scr_led_parallel
    options.row_address_type = const.scr_row_address_type
    options.multiplexing = const.scr_led_multiplexing
    options.pwm_bits = const.scr_led_pwm_bits
    options.brightness = _state.currentBrightness
    options.pwm_lsb_nanoseconds = const.scr_led_pwm_lsb_nanoseconds
    options.led_rgb_sequence = const.scr_led_rgb_sequence
    if const.scr_led_show_refresh:
        options.show_refresh_rate = 1
    if const.scr_led_slowdown_gpio is not None:
        options.gpio_slowdown = const.scr_led_slowdown_gpio
    if const.scr_led_no_hardware_pulse:
        options.disable_hardware_pulsing = True
    options.pixel_mapper_config = const.scr_pixel_mapper_config

    # https://github.com/hzeller/rpi-rgb-led-matrix/issues/679#issuecomment-423268899
    _state.matrix = RGBMatrix(options=options)

    for fontFilename in ["10x20", "6x9"]:
        font = graphics.Font()
        font.LoadFont("{}/{}.bdf".format(const.scr_fonts_dir, fontFilename))
        _state.fonts.append(font)

    logger.debug("matrix canvas initialized")


# =============================================================================


def do_iterate():
    global _state

    # will happen once...
    if _state.matrix is None:
        init_matrix()
        init_timer_ticks()
        drawClock()
        _notifyEventLuxUpdateRequest()

    try:
        cmdDill = _state.cmdq.get(True, TIMERTICK_UNIT)
        cmdFun, params = dill.loads(cmdDill)
        cmdFun(*params)
    except queue.Empty:
        pass
    except (KeyboardInterrupt, SystemExit):
        return
    timer_tick()


def timer_tick_always():
    adjustBrightness()


def timer_tick_250ms():
    # drawLineAnimation()
    updateMotionPixel()
    pass


def timer_tick_500ms():
    pass


def timer_tick_1sec():
    updateBrightnessTimeoutInSeconds()
    pass


def timer_tick_15sec():
    drawClock()
    pass


def timer_tick_1min():
    pass


class TimerTickService(object):
    def __init__(self, intervalInMilliseconds, fun, now=datetime.now()):
        self.intervalInMilliseconds = intervalInMilliseconds
        self.fun = fun
        self.nextExpiration = datetime.now() + timedelta(
            0, 0, intervalInMilliseconds * 1000
        )


def init_timer_ticks():
    global _state
    _state.timer_tick_services = [
        TimerTickService(250, timer_tick_250ms),
        TimerTickService(500, timer_tick_500ms),
        TimerTickService(1000, timer_tick_1sec),
        TimerTickService(15000, timer_tick_15sec),
        TimerTickService(60000, timer_tick_1min),
    ]


def timer_tick():
    global _state

    timer_tick_always()
    for timer_tick_service in _state.timer_tick_services:
        now = datetime.now()
        if timer_tick_service.nextExpiration <= now:
            timer_tick_service.fun()
            timer_tick_service.nextExpiration = now + timedelta(
                0, 0, timer_tick_service.intervalInMilliseconds * 1000
            )


# ----------------------------------------------------------------------


def adjustBrightness():
    global _state

    # if brightness is already where we want it to be, we are done
    if _state.currentBrightness == _state.wantedBrightness:
        return

    brightIncr = {True: -1}.get(_state.wantedBrightness < _state.currentBrightness, 1)
    _state.currentBrightness += brightIncr
    drawClock()

    if _state.currentBrightness == _state.wantedBrightness:
        logger.debug(
            "curr brightness reached target value of {}".format(_state.wantedBrightness)
        )
        # Reaching target also has side effect of forcing a draw of the clock face
        if _state.currentBrightness:
            drawClock()
    else:
        # queue an event to self, so we are not bound to wait for TIMERTICK_UNIT timeout.
        # Note that this will cause timer_tick to be called twice in do_iterate(). No biggie.
        if _state.cmdq.empty():
            _enqueue_cmd((timer_tick, []))


def updateBrightnessTimeoutInSeconds():
    global _state
    if _state.stayOnCurrentBrightnessTimeout > 0:
        _state.stayOnCurrentBrightnessTimeout -= 1
        if _state.stayOnCurrentBrightnessTimeout != 0:
            return
        # update wanted brightness to what lux has determined it to be?
        if _state.useLuxToDetermineBrightness:
            _notifyEventLuxUpdateRequest()
        logger.info("stayOnCurrentBrightnessTimeout is now zero")


def checkForDisplayWakeup(prevProximity, currProximity):
    global _state

    if currProximity < prevProximity:
        return

    _state.stayOnCurrentBrightnessTimeout = const.scr_wakeupTimeoutInSeconds
    jumpstartCurrentBrightness = int(const.scr_brightnessMaxValue / 6)
    _state.currentBrightness = max(jumpstartCurrentBrightness, _state.currentBrightness)
    _state.wantedBrightness = const.scr_brightnessMaxValue
    adjustBrightness()
    logger.info("woke screen up")


def updateMotionPixel(canvas=None):
    global _state

    if canvas is None:
        canvas = _state.matrix
    data = _state.timer_tick_data

    # turn motion detected pixel on/off
    # if it was already off and it is still off, this is a noop
    # it is possible canvas has been cleared, so if it is supposed to be
    # on, make it so every time
    currMotionPixelIsTurnedOn = data.get("motionPixelIsTurnedOn", True)
    newMotionPixelIsTurnedOn = _state.cachedProximity != 0
    if newMotionPixelIsTurnedOn or currMotionPixelIsTurnedOn:
        r, g, b = 0, 0, {True: 123}.get(newMotionPixelIsTurnedOn, 0)
        canvas.SetPixel(canvas.width - 1, canvas.height - 1, r, g, b)
        data["motionPixelIsTurnedOn"] = newMotionPixelIsTurnedOn


def drawLineAnimation(canvas=None, counterIncr=1):
    global _state

    if canvas is None:
        canvas = _state.matrix
    data = _state.timer_tick_data

    drawLineAnimationCounter = data.get("drawLineAnimationCounter", 1)
    data["drawLineAnimationCounter"] = drawLineAnimationCounter + counterIncr
    red = data.get("red")

    if drawLineAnimationCounter >= canvas.height:
        data["drawLineAnimationCounter"] = 0
        graphics.DrawLine(canvas, 0, 0, 0, canvas.height, data.get("black"))
    else:
        graphics.DrawLine(
            canvas, 0, 0, 0, drawLineAnimationCounter % canvas.height, red
        )


def drawClock():
    global _state

    # try to avoid memleak by reusing previous frame canvas
    data = _state.timer_tick_data
    canvas = data.get("previousFrameCanvas")
    if canvas is None:
        canvas = _state.matrix.CreateFrameCanvas()
    else:
        # re-use, recycle
        canvas.Clear()
    if _state.currentBrightness != const.scr_brightnessOff:
        _drawClock2(canvas, data, _state)
    else:
        canvas.brightness = const.scr_brightnessMinValue
    updateMotionPixel(canvas)
    data["previousFrameCanvas"] = _state.matrix.SwapOnVSync(canvas)


def _drawClock2(canvas, data, _state):
    font0 = _state.fonts[0]
    font1 = _state.fonts[1]
    green = data.get("green")
    blue = data.get("blue")
    red = data.get("red")

    canvas.brightness = _state.currentBrightness

    # baseline y axis position can be between 13 and 44
    baseClockPosY = data.get("baseClockPosY", 28)

    # datetime format. Ref: http://strftime.org/  and https://pymotw.com/2/datetime/
    now = datetime.now()
    # remove '0' pad from hour's format
    clock = now.strftime("%-I:%M")
    amPm = now.strftime("%p").lower()
    clockColor, dateColor = {"am": (green, red), "pm": (red, green)}.get(
        amPm, (blue, blue)
    )
    posX = getCenterPosX(canvas, font0, clock)
    # canvas, font, x, y, color, text
    graphics.DrawText(canvas, font0, posX, baseClockPosY, clockColor, clock)

    # Weekday
    weekday = now.strftime("%A")
    posX = getCenterPosX(canvas, font1, weekday)
    graphics.DrawText(canvas, font1, posX, baseClockPosY + 9, blue, weekday)

    # Date
    cal = now.strftime("%-d / %b")
    posX = getCenterPosX(canvas, font1, cal)
    graphics.DrawText(canvas, font1, posX, baseClockPosY + 18, dateColor, cal)


def getCenterPosX(canvas, font, msg):
    numberOfChars = len(msg)
    pixelsUsed = numberOfChars * font.CharacterWidth(0)
    if pixelsUsed >= canvas.width:
        return 0
    return int((canvas.width - pixelsUsed) / 2)


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
def do_handle_screen_stays_on(enable):
    logger.debug("queuing screen stays on {}".format(enable))
    params = [enable]
    return _enqueue_cmd((_do_handle_screen_stays_on, params))


def _do_handle_screen_stays_on(enable):
    global _state
    stayOnInDarkRoomFun = lambda x: True if x else False
    _state.stayOnInDarkRoom = stayOnInDarkRoomFun(enable)
    logger.info("stay on in dark room is now {}".format(_state.stayOnInDarkRoom))
    # update wanted brightness to what lux has determined it to be?
    if _state.useLuxToDetermineBrightness:
        _notifyEventLuxUpdateRequest()


# called from outside this module
def do_handle_motion_proximity(currProximity=0):
    logger.debug("queuing motion_proximity {}".format(currProximity))
    params = [currProximity]
    return _enqueue_cmd((_do_handle_motion_proximity, params))


def _do_handle_motion_proximity(currProximity):
    global _state
    prevProximity = _state.cachedProximity
    logger.debug(
        "motion_proximity set from {} to {}".format(prevProximity, currProximity)
    )
    _state.cachedProximity = currProximity
    checkForDisplayWakeup(prevProximity, currProximity)


# called from outside this module
def do_handle_motion_lux(currLux=0):
    logger.debug("queuing motion_lux {}".format(currLux))
    params = [currLux]
    return _enqueue_cmd((_do_handle_motion_lux, params))


def _do_handle_motion_lux(currLux):
    global _state
    # map lux values into a percentage. The brighter the room, the more
    # intensity we will need for the matrix display
    currNormalizedLux = normalizedLux(currLux, _state.stayOnInDarkRoom)
    if _state.cachedNormalizedLux == currNormalizedLux:
        logger.debug(
            "motion_lux raw {} remains normalized as {}".format(
                currLux, currNormalizedLux
            )
        )
    else:
        logger.info(
            "motion_lux raw {} set normalized from {} to {}".format(
                currLux, _state.cachedNormalizedLux, currNormalizedLux
            )
        )
        _state.cachedNormalizedLux = currNormalizedLux

    if (
        _state.useLuxToDetermineBrightness
        and _state.stayOnCurrentBrightnessTimeout == 0
    ):
        _state.wantedBrightness = _state.cachedNormalizedLux


def normalizedLux(rawLux, stayOnInDarkRoom):
    # exception case: if rawLux is less than dark room threshold turn display off
    if rawLux <= const.motion_luxDarkRoomThreshold and not stayOnInDarkRoom:
        return const.scr_brightnessOff
    # make sure raw value falls within expected range
    x = min(const.motion_luxMaxValue, max(const.motion_luxMinValue, rawLux))
    # Ref: https://stackoverflow.com/questions/1969240/mapping-a-range-of-values-to-another
    a, b = const.motion_luxMinValue, const.motion_luxMaxValue
    c, d = const.scr_brightnessMinValue, const.scr_brightnessMaxValue
    return int((x - a) / (b - a) * (d - c) + c)


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
    while not stop_trigger:
        do_iterate()
