"""state classes"""

from abc import ABC, abstractmethod


class State:
    def __init__(self):
        pass

    @abstractmethod
    def handle(self):
        pass


class SleepState(State):
    def handle(self, action):
        """process actions in sleeping state"""


class AwakeState(State):
    def handle(self, action):
        """process actions in awake state"""
