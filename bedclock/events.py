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
