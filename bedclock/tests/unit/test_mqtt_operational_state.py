import dill

from six.moves import queue

from bedclock import const
from bedclock import mqttclient


class FakeClock(object):
    def __init__(self, now=0):
        self.now = now

    def __call__(self):
        return self.now


class FakePublishInfo(object):
    def wait_for_publish(self):
        pass


class FakeMqttClient(object):
    def __init__(self, fail_topics=None):
        self.published = []
        self.fail_topics = set(fail_topics or [])
        self.loop_started = False

    def loop_start(self):
        self.loop_started = True

    def publish(self, topic, value, qos):
        self.published.append((topic, value, qos))
        if topic in self.fail_topics:
            raise RuntimeError("publish failed")
        return FakePublishInfo()


class FakeCommandQueue(object):
    def __init__(self, commands=None):
        self.commands = list(commands or [])
        self.timeouts = []

    def get(self, block, timeout):
        self.timeouts.append(timeout)
        if self.commands:
            return self.commands.pop(0)
        raise queue.Empty()

    def put_nowait(self, item):
        self.commands.append(item)


def setup_state(clock, cmdq=None):
    mqttclient.do_init(monotonic_clock=clock)
    mqttclient._state.mqtt_client = FakeMqttClient()
    mqttclient._state.cmdq = cmdq or FakeCommandQueue()


def command(fun, params):
    return dill.dumps((fun, params))


def patch_collectors(monkeypatch, uptime=10, mem=20):
    monkeypatch.setattr(mqttclient.systemstats, "read_uptime_minutes", lambda: uptime)
    monkeypatch.setattr(mqttclient.systemstats, "read_mem_available_kb", lambda: mem)


def test_no_operational_report_before_complete_interval(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)
    patch_collectors(monkeypatch)

    clock.now = const.oper_stateReportPeriodInSeconds - 1
    mqttclient.do_iterate()

    assert mqttclient._state.mqtt_client.published == []


def test_both_operational_topic_keys_are_attempted_when_deadline_reached(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)
    patch_collectors(monkeypatch, uptime=123, mem=456)

    clock.now = const.oper_stateReportPeriodInSeconds
    mqttclient.do_iterate()

    assert mqttclient._state.mqtt_client.published == [
        ("/bedclock/oper_uptime_minutes", 123, mqttclient.TOPIC_QOS),
        ("/bedclock/oper_state/mem_available_kb", 456, mqttclient.TOPIC_QOS),
    ]


def test_next_deadline_is_scheduled_after_reporting_cycle(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)
    patch_collectors(monkeypatch)

    clock.now = const.oper_stateReportPeriodInSeconds + 99
    mqttclient.do_iterate()

    assert mqttclient._state.next_oper_state_report == (
        clock.now + const.oper_stateReportPeriodInSeconds
    )


def test_delayed_process_publishes_one_cycle_not_catch_up_burst(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)
    patch_collectors(monkeypatch)

    clock.now = const.oper_stateReportPeriodInSeconds * 4
    mqttclient.do_iterate()

    assert len(mqttclient._state.mqtt_client.published) == 2


def test_busy_command_queue_cannot_starve_operational_report(monkeypatch):
    clock = FakeClock(0)
    cmdq = FakeCommandQueue([
        command(mqttclient._mqtt_publish_value, [const.mqtt_topic_pub_light, 100])
    ])
    setup_state(clock, cmdq)
    patch_collectors(monkeypatch, uptime=1, mem=2)

    clock.now = const.oper_stateReportPeriodInSeconds
    mqttclient.do_iterate()

    assert mqttclient._state.mqtt_client.published == [
        ("/bedclock/light", 100, mqttclient.TOPIC_QOS),
        ("/bedclock/oper_uptime_minutes", 1, mqttclient.TOPIC_QOS),
        ("/bedclock/oper_state/mem_available_kb", 2, mqttclient.TOPIC_QOS),
    ]


def test_lux_publications_do_not_trigger_or_postpone_operational_reporting(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)
    patch_collectors(monkeypatch)
    initial_deadline = mqttclient._state.next_oper_state_report

    assert mqttclient.do_handle_motion_lux(365) is True
    assert mqttclient._state.next_oper_state_report == initial_deadline
    assert mqttclient._state.mqtt_client.published == []

    clock.now = initial_deadline - 1
    mqttclient.do_iterate()
    assert mqttclient._state.next_oper_state_report == initial_deadline


def test_uptime_collection_failure_does_not_suppress_memory(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)

    def fail_uptime():
        raise ValueError("bad uptime")

    monkeypatch.setattr(mqttclient.systemstats, "read_uptime_minutes", fail_uptime)
    monkeypatch.setattr(mqttclient.systemstats, "read_mem_available_kb", lambda: 456)

    clock.now = const.oper_stateReportPeriodInSeconds
    mqttclient.do_iterate()

    assert mqttclient._state.mqtt_client.published == [
        ("/bedclock/oper_state/mem_available_kb", 456, mqttclient.TOPIC_QOS),
    ]


def test_memory_collection_failure_does_not_suppress_uptime(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)

    monkeypatch.setattr(mqttclient.systemstats, "read_uptime_minutes", lambda: 123)

    def fail_mem():
        raise ValueError("bad meminfo")

    monkeypatch.setattr(mqttclient.systemstats, "read_mem_available_kb", fail_mem)

    clock.now = const.oper_stateReportPeriodInSeconds
    mqttclient.do_iterate()

    assert mqttclient._state.mqtt_client.published == [
        ("/bedclock/oper_uptime_minutes", 123, mqttclient.TOPIC_QOS),
    ]


def test_collection_or_publishing_failure_does_not_tight_retry_loop(monkeypatch):
    clock = FakeClock(0)
    setup_state(clock)
    mqttclient._state.mqtt_client = FakeMqttClient(
        fail_topics=["/bedclock/oper_uptime_minutes"]
    )
    patch_collectors(monkeypatch, uptime=123, mem=456)

    clock.now = const.oper_stateReportPeriodInSeconds
    mqttclient.do_iterate()
    first_deadline = mqttclient._state.next_oper_state_report
    mqttclient.do_iterate()

    assert first_deadline == clock.now + const.oper_stateReportPeriodInSeconds
    assert len(mqttclient._state.mqtt_client.published) == 2


def test_existing_light_publication_behavior_remains_queued():
    clock = FakeClock(0)
    setup_state(clock)

    assert mqttclient.do_handle_motion_lux(777) is True
    cmd_fun, params = dill.loads(mqttclient._state.cmdq.commands[0])

    assert cmd_fun == mqttclient._mqtt_publish_value
    assert params == [const.mqtt_topic_pub_light, 777]


def test_queue_wait_timeout_is_limited_by_operational_deadline():
    clock = FakeClock(0)
    cmdq = FakeCommandQueue()
    setup_state(clock, cmdq)

    clock.now = const.oper_stateReportPeriodInSeconds - 5
    mqttclient.do_iterate()

    assert cmdq.timeouts == [5]


def test_operational_topic_strings_are_generated_exactly():
    assert const.mqtt_topics_pub[const.mqtt_topic_pub_oper_uptime_minutes] == (
        "/bedclock/oper_uptime_minutes"
    )
    assert const.mqtt_topics_pub[const.mqtt_topic_pub_oper_mem_available_kb] == (
        "/bedclock/oper_state/mem_available_kb"
    )
