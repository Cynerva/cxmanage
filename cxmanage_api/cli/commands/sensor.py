"""Calxeda: sensor.py"""


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


from cxmanage import get_tftp, get_nodes, get_node_strings, run_command

# pylint: disable=R0914
def sensor_command(args):
    """read sensor values from a cluster or host"""
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Getting sensor readings..."
    results, errors = run_command(args, nodes, "get_sensors",
            args.sensor_name)

    sensors = {}
    for node in nodes:
        if node in results:
            for sensor_name, sensor in results[node].iteritems():
                if not sensor_name in sensors:
                    sensors[sensor_name] = []

                reading = sensor.sensor_reading.replace("(+/- 0) ", "")
                try:
                    value = float(reading.split()[0])
                    suffix = reading.lstrip("%f " % value)
                    sensors[sensor_name].append((node, value, suffix))
                except ValueError:
                    sensors[sensor_name].append((node, reading, ""))

    node_strings = get_node_strings(args, results, justify=True)
    jsize = len(node_strings.itervalues().next())
    for sensor_name, readings in sensors.iteritems():
        print sensor_name

        for node, reading, suffix in readings:
            print "%s: %.2f %s" % (node_strings[node], reading, suffix)

        try:
            if all(suffix == x[2] for x in readings):
                minimum = min(x[1] for x in readings)
                maximum = max(x[1] for x in readings)
                average = sum(x[1] for x in readings) / len(readings)
                print "%s: %.2f %s" % ("Minimum".ljust(jsize), minimum, suffix)
                print "%s: %.2f %s" % ("Maximum".ljust(jsize), maximum, suffix)
                print "%s: %.2f %s" % ("Average".ljust(jsize), average, suffix)
        except ValueError:
            pass

        print

    if not args.quiet and errors:
        print "Some errors occured during the command.\n"

    return len(errors) > 0
