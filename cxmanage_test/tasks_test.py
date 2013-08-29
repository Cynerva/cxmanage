"""Calxeda: task_test.py"""


# Copyright (c) 2012, Calxeda Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# * Neither the name of Calxeda Inc. nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.


import unittest
import time

from cxmanage_api.tasks import TaskQueue


# pylint: disable=R0904
class TaskTest(unittest.TestCase):
    """Test for the TaskQueue Class."""

    def test_task_queue(self):
        """ Test the task queue """
        task_queue = TaskQueue()
        counters = [Counter() for _ in xrange(128)]
        tasks = [task_queue.put(counters[i].add, i) for i in xrange(128)]

        for task in tasks:
            task.join()

        for i in xrange(128):
            self.assertEqual(counters[i].value, i)

    def test_sequential_delay(self):
        """ Test that a single thread delays between tasks """
        task_queue = TaskQueue(threads=1, delay=0.25)
        counters = [Counter() for x in xrange(8)]

        start = time.time()

        tasks = [task_queue.put(x.add, 1) for x in counters]
        for task in tasks:
            task.join()

        finish = time.time()

        self.assertGreaterEqual(finish - start, 2.0)


# pylint: disable=R0903
class Counter(object):
    """ Simple counter object for testing purposes """
    def __init__(self):
        self.value = 0

    def add(self, value):
        """ Increment this counter's value by some amount """
        self.value += value
