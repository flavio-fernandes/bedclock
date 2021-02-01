#!/usr/bin/env python3


class Base(object):
    def __init__(self, description, value=None):
        self.name = self.__class__.__name__
        self.description = description
        self.value = value


class MotionLux(Base):
    def __init__(self, currLux):
        Base.__init__(self,
                      "motion detector current lux is {}".format(currLux),
                      currLux)


class MotionProximity(Base):
    def __init__(self, currProximity):
        Base.__init__(self,
                      "motion detector proximity at {}".format(currProximity),
                      currProximity)


class MotionDetected(Base):
    def __init__(self):
        Base.__init__(self, "motion detected")


class LuxUpdateRequest(Base):
    def __init__(self, requester="anonymous"):
        Base.__init__(self, "lux update requested by {}".format(requester))


class ScreenStaysOn(Base):
    def __init__(self, enable, requester="anonymous"):
        Base.__init__(self,
                      "screen stays on {} requested by {}".format(enable, requester),
                      enable)


class OutsideTemperature(Base):
    def __init__(self, temperature, requester="anonymous"):
        Base.__init__(self,
                      "outside temperature update to {} by {}".format(temperature, requester),
                      temperature)


class DisplayMessage(Base):
    def __init__(self, message, requester="anonymous"):
        Base.__init__(self,
                      "set screen display message to '{}' by {}".format(message, requester),
                      message)
