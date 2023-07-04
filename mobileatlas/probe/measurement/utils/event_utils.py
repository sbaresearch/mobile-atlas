#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Defines Events
"""
import threading
from time import perf_counter


# Create negatable event
class NegatableEvent:
    def __init__(self):
        self._event = threading.Event()
        self._not_event = threading.Event()
        self._not_event.set()

    def is_set(self):
        return self._event.is_set()

    def set(self):
        self._not_event.clear()
        self._event.set()

    def clear(self):
        self._event.clear()
        self._not_event.set()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def wait_false(self, timeout=None):
        return self._not_event.wait(timeout)

class EnhancedEvent:
    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._timestamp = None

    def _reset_internal_locks(self):
        # private!  called by Thread._reset_internal_locks by _after_fork()
        self._cond.__init__(threading.Lock())

    def is_set(self):
        return self._timestamp is not None

    def is_cleared(self):
        return self._timestamp is None

    def set(self):
        with self._cond:
            self._timestamp = perf_counter()
            self._cond.notify_all()

    def clear(self):
        with self._cond:
            self._timestamp = None
            self._cond.notify_all()

    def wait(self, timeout=None):
        with self._cond:
            if self._timestamp is None:
                return self._cond.wait_for(self.is_set, timeout)
            return True

    def wait_cleared(self, timeout=None):
        with self._cond:
            if self._timestamp is not None:
                return self._cond.wait_for(self.is_cleared, timeout)
            return True

    def wait_debounced(self, timeout=None, debounce_interval = 0, retry=True):
        #assert timeout > debounce_interval, "timeout needs to be bigger than debounce_interval"
        if not debounce_interval:
            return self.wait(timeout)
        with self._cond:
            time_start = perf_counter()
            if self._timestamp is None and not self._cond.wait_for(self.is_set, timeout):
                return False
            interval_set = perf_counter() - self._timestamp
            if interval_set >= debounce_interval:
                return True
            debounce_left = debounce_interval - interval_set
            if self._cond.wait_for(self.is_cleared, debounce_left):
                if not retry:
                    return False
                time_elapsed = perf_counter() - time_start # xx seconds of timeout already passed
                time_left = timeout - time_elapsed
                return self.wait_debounced(time_left, debounce_interval)
            return True
            

# Create a unified OrEvent from a list of regular events
class Events:
    # Define versions of set and clear that trigger a "change" callback
    @staticmethod
    def or_set(e):
        e._set()
        e.changed()

    @staticmethod
    def or_clear(e):
        e._clear()
        e.changed()

    def __init__(self, events):
        self.events = events
        self.or_event = threading.Event()

        for event in self.events:
            self.orify(event)

        # initialize
        self.changed()

    def __del__(self):
        self.deorify_all()

    def add_event(self, event):
        if event not in self.events:
            self.events.add(event)
            self.orify(event)
            self.changed()

    def set_all(self):
        for event in self.events:
            event.set()

    def clear_all(self):
        for event in self.events:
            event.clear()

    def deorify_all(self):
        for event in self.events:
            self.deorify(event)

    # any time a constituent event is set or cleared, update this one
    def changed(self):
        bools = [event.is_set() for event in self.events]
        if any(bools):
            self.or_event.set()
        else:
            self.or_event.clear()

    # Make sets and clears trigger a "changed" callback that notifies an OrEvent
    # of a change. Copy original "set" and "clear" so they can still be called.
    def orify(self, event):
        event._set = event.set
        event._clear = event.clear
        event.changed = self.changed
        event.set = lambda: Events.or_set(event)
        event.clear = lambda: Events.or_clear(event)

    def deorify(self, event):
        event.set = event._set
        event.clear = event._clear

    # wrapper functions:
    def is_set(self):
        return self.or_event.is_set()
    isSet = is_set

    def set(self):
        return self.or_event.set()

    def clear(self):
        return self.or_event.clear()

    def wait(self, timeout=None):
        return self.or_event.wait(timeout)


def wait_on(name, e):
    print("Waiting on %s..." % (name,))
    e.wait()
    print("%s fired!" % (name,))

# just for or_event
def test_or():
    import time

    e1 = threading.Event()
    e2 = threading.Event()

    or_e = Events([e1, e2])

    threading.Thread(target=wait_on, args=('e1', e1)).start()
    time.sleep(0.05)
    threading.Thread(target=wait_on, args=('e2', e2)).start()
    time.sleep(0.05)
    threading.Thread(target=wait_on, args=('or_e', or_e)).start()
    time.sleep(0.05)

    print("Firing e1 in 2 seconds...")
    time.sleep(2)
    e1.set()
    time.sleep(0.05)

    print("Firing e2 in 2 seconds...")
    time.sleep(2)
    e2.set()
    time.sleep(0.05)


if __name__ == "__main__":
    test_or()
