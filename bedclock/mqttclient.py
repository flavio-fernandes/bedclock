#!/usr/bin/env python3

import dill
import multiprocessing
import os
import paho.mqtt.client as mqtt
import signal
from six.moves import queue
import sys
import time

from bedclock import const
from bedclock import events
from bedclock import log

CMDQ_SIZE = 10  # max pending events
CMDQ_GET_TIMEOUT = 3600  # seconds
TOPIC_QOS = 1
STATE_ON = "on"
STATE_OFF = "off"
MAX_PAYLOAD_SIZE = 2048
_state = None


class State(object):
    def __init__(self, queueEventFun, mqtt_broker_ip):
        self.queueEventFun = queueEventFun  # queue for output events
        self.cmdq = multiprocessing.Queue(CMDQ_SIZE)  # queue for input commands
        self.mqtt_broker_ip = mqtt_broker_ip
        self.mqtt_client = None


# =============================================================================


def do_init(queueEventFun=None, mqtt_broker_ip=const.mqtt_broker_ip):
    global _state
    _state = State(queueEventFun, mqtt_broker_ip)
    # logger.debug("mqttclient init called")


# =============================================================================


def _notifyEvent(event):
    global _state
    if _state.queueEventFun:
        logger.debug("generating event: {}".format(event.name))
        _state.queueEventFun(event)


# =============================================================================


def client_connect_callback(client, userdata, flags_dict, rc):
    if rc != mqtt.MQTT_ERR_SUCCESS:
        logger.warning(
            "client connect failed with flags %s rc %s %s",
            flags_dict,
            rc,
            mqtt.error_string(rc),
        )
        return
    logger.info("client connected with flags %s rc %s", flags_dict, rc)
    bedclock_topics = [(t, TOPIC_QOS) for t in const.mqtt_topics_sub.values()]
    client.subscribe(bedclock_topics)
    # artificially publish a motion off, just to trigger something
    do_motion_off()


def client_message_callback(client, userdata, msg):
    logger.debug("callback for mqtt message %s %s", msg.topic, msg.payload)
    params = [msg.topic, msg.payload]
    _enqueue_cmd((_do_handle_mqtt_msg, params))


def _setup_mqtt_client(broker_ip):
    try:
        client = mqtt.Client(client_id="bedclock")
        client.on_connect = client_connect_callback
        client.on_message = client_message_callback

        client.connect_async(broker_ip, port=1883, keepalive=181)
        return client
    except Exception as e:
        logger.info("mqtt client setup did not work %s", e)
    return None


# =============================================================================


def do_iterate():
    global _state

    if not _state.mqtt_client:
        _state.mqtt_client = _setup_mqtt_client(_state.mqtt_broker_ip)
        if not _state.mqtt_client:
            logger.warning("got no mqttt client")
            time.sleep(30)
            return
        logger.debug("have a mqtt_client now")
        _state.mqtt_client.loop_start()

    try:
        cmdDill = _state.cmdq.get(True, CMDQ_GET_TIMEOUT)
        cmdFun, params = dill.loads(cmdDill)
        cmdFun(*params)
        logger.debug("executed a lambda command with params %s", params)
    except queue.Empty:
        # logger.debug("mqttclient iterate noop")
        pass
    except (KeyboardInterrupt, SystemExit):
        pass


# =============================================================================


def _do_handle_mqtt_msg_stay(msg):
    enable = isinstance(msg, str) and msg.lower() in const.mqtt_value_enable
    requester = os.path.split(__file__)[-1]
    requester = requester.split(".py")[0]
    event = events.ScreenStaysOn(enable, requester)
    _notifyEvent(event)


def _do_handle_mqtt_msg(topic, payload):
    # logger.debug("received mqtt message %s %s", topic, payload)

    # paranoid: ignore big payloads
    payloadSize = sys.getsizeof(payload)
    if payloadSize > MAX_PAYLOAD_SIZE:
        logger.warning("ignoring msg for {}: {} payload too big", topic, payloadSize)
        return
    if isinstance(payload, bytes):
        payload = payload.decode("ascii")

    tp = lambda x: const.mqtt_topics_sub.get(x)
    msg_handlers = {tp(const.mqtt_topic_sub_stay): _do_handle_mqtt_msg_stay}

    msg_handler = msg_handlers.get(topic)
    if msg_handler:
        logger.debug("handling mqtt message %s %s", topic, payload)
        msg_handler(payload)


def _mqtt_publish_value(publish_topic_key, newValue):
    global _state
    topic = const.mqtt_topics_pub.get(publish_topic_key)
    if not topic:
        # bug!?!
        logger.error("no mqtt topic for %s %s", publish_topic_key, newValue)
        return
    if not _state.mqtt_client:
        logger.warning("no client to publish mqtt topic %s %s", topic, newValue)
        return
    try:
        # logger.debug("publishing mqtt topic %s %s", topic, newValue)
        info = _state.mqtt_client.publish(topic, newValue, qos=TOPIC_QOS)
        info.wait_for_publish()
    except Exception as e:
        logger.error("client failed publish mqtt topic %s %s %s", topic, newValue, e)
        return
    logger.debug("published mqtt topic %s %s", topic, newValue)


# =============================================================================


def _enqueue_cmd(l):
    global _state
    if not const.mqtt_enabled:
        return True  # noop
    lDill = dill.dumps(l)
    try:
        _state.cmdq.put_nowait(lDill)
    except queue.Full:
        logger.error("command queue is full: cannot add")
        return False
    return True


# called from outside this module
def do_motion_on():
    return _do_motion_onoff(STATE_ON)


# called from outside this module
def do_motion_off():
    return _do_motion_onoff(STATE_OFF)


def _do_motion_onoff(newState):
    logger.debug("queuing motion_{}".format(newState))
    params = [const.mqtt_topic_pub_motion, newState]
    return _enqueue_cmd((_mqtt_publish_value, params))


# called from outside this module
def do_handle_motion_lux(currLux):
    logger.debug("queuing motion_lux {}".format(currLux))
    params = [const.mqtt_topic_pub_light, currLux]
    return _enqueue_cmd((_mqtt_publish_value, params))


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
