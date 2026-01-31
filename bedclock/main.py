#!/usr/bin/env python3

import multiprocessing
from six.moves import queue
import sys
import os

# need this because exported python path gets lost when invoking sudo
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from bedclock import const  # noqa
from bedclock import events  # noqa
from bedclock import log  # noqa
from bedclock import mqttclient  # noqa
from bedclock import screen  # noqa
from bedclock import motion  # noqa

EVENTQ_SIZE = 1000
EVENTQ_GET_TIMEOUT = 15  # seconds


class ProcessBase(multiprocessing.Process):
    def __init__(self, eventq):
        multiprocessing.Process.__init__(self)
        self.eventq = eventq

    def putEvent(self, event):
        try:
            self.eventq.put_nowait(event)
        except queue.Full:
            logger.error(
                "Exiting: Queue is stuck, cannot add event: %s %s",
                event.name,
                event.description,
            )
            raise RuntimeError("Main process has a full event queue")


class MqttclientProcess(ProcessBase):
    def __init__(self, eventq):
        ProcessBase.__init__(self, eventq)
        mqttclient.do_init(self.putEvent)

    def run(self):
        logger.debug("mqttclient process started")
        while True:
            mqttclient.do_iterate()


class MotionProcess(ProcessBase):
    def __init__(self, eventq):
        ProcessBase.__init__(self, eventq)
        motion.do_init(self.putEvent)

    def run(self):
        logger.debug("motion process started")
        motion.do_lux_notify_on()
        motion.do_motion_notify_on()
        while True:
            motion.do_iterate()


class ScreenProcess(ProcessBase):
    def __init__(self, eventq):
        ProcessBase.__init__(self, eventq)
        screen.do_init(self.putEvent)

    def run(self):
        logger.debug("screen process started")
        while True:
            screen.do_iterate()


def processMotionLux(event):
    screen.do_handle_motion_lux(event.value)
    mqttclient.do_handle_motion_lux(event.value)


def processMotionDetected(_event):
    mqttclient.do_motion_on()


def processMotionProximity(event):
    screen.do_handle_motion_proximity(event.value)
    if not event.value:
        mqttclient.do_motion_off()


def processLuxUpdateRequest(event):
    logger.debug("Handling event {}".format(event.description))
    motion.do_lux_report()


def processScreenStaysOn(event):
    logger.debug("Handling event {}".format(event.description))
    screen.do_handle_screen_stays_on(event.value)


def processOutsideTemperature(event):
    logger.debug("Handling event {}".format(event.description))
    screen.do_handle_outside_temperature(event.value)


def processDisplayMessage(event):
    logger.debug("Handling event {}".format(event.description))
    screen.do_handle_display_message(event.value)


def processEvent(event):
    # Based on the event, call lambda(s) to handle
    syncFunHandlers = {
        "MotionLux": [processMotionLux],
        "MotionDetected": [processMotionDetected],
        "MotionProximity": [processMotionProximity],
        "LuxUpdateRequest": [processLuxUpdateRequest],
        "ScreenStaysOn": [processScreenStaysOn],
        "OutsideTemperature": [processOutsideTemperature],
        "DisplayMessage": [processDisplayMessage],
    }
    cmdFuns = syncFunHandlers.get(event.name)
    if not cmdFuns:
        logger.warning(
            "Don't know how to process event %s: %s", event.name, event.description
        )
        return
    for cmdFun in cmdFuns:
        if cmdFun is not None:
            cmdFun(event)


def processEvents(timeout):
    global stop_trigger
    try:
        event = eventq.get(True, timeout)
        # logger.debug("Process event for %s", type(event))
        if isinstance(event, events.Base):
            processEvent(event)
        else:
            logger.warning("Ignoring unexpected event: %s", event)
    except (KeyboardInterrupt, SystemExit):
        logger.info("got KeyboardInterrupt")
        stop_trigger = True
    except queue.Empty:
        # make sure children are still running
        for p in myProcesses:
            if p.is_alive():
                continue
            logger.error("%s child died", p.__class__.__name__)
            logger.info("exiting so systemd can restart")
            raise RuntimeError("Child process terminated unexpectedly")


def main():
    try:
        # Start our processes
        [p.start() for p in myProcesses]
        logger.debug("Starting main event processing loop")
        while not stop_trigger:
            processEvents(EVENTQ_GET_TIMEOUT)
    except Exception as e:
        logger.error("Unexpected event: %s", e)
    # make sure all children are terminated
    [p.terminate() for p in myProcesses]


# globals
stop_trigger = False
logger = None
eventq = None
myProcesses = []


if __name__ == "__main__":
    # global logger, eventq, myProcesses

    logger = log.getLogger()
    log.initLogger()
    logger.debug("bedclock process started")
    eventq = multiprocessing.Queue(EVENTQ_SIZE)
    if const.mqtt_enabled:
        myProcesses.append(MqttclientProcess(eventq))
    myProcesses.append(MotionProcess(eventq))
    myProcesses.append(ScreenProcess(eventq))
    main()
    raise RuntimeError("main is exiting")
