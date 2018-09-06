#!/usr/bin/env python3
import logging
from logging.handlers import SysLogHandler


def getLogger():
    return logging.getLogger('bedclock')


def initLogger():
    logger = getLogger()
    logger.setLevel(logging.DEBUG)

    # Logs are normally configured here: /etc/rsyslog.d/*
    syslog = SysLogHandler(address="/run/systemd/journal/syslog",
                           facility=SysLogHandler.LOG_DAEMON)
    format = '%(asctime)s [bedclock] %(module)12s:%(lineno)-d %(levelname)-8s %(message)s'
    formatter = logging.Formatter(format)
    syslog.setFormatter(formatter)
    logger.addHandler(syslog)
