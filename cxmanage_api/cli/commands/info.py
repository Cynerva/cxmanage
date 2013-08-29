"""Calxeda: info.py"""


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


from cxmanage_api.cli import get_tftp, get_nodes, get_node_strings, \
        run_command, COMPONENTS


def info_command(args):
    """print info from a cluster or host"""
    if args.info_type in [None, 'basic']:
        return info_basic_command(args)
    elif args.info_type == 'ubootenv':
        return info_ubootenv_command(args)


def info_basic_command(args):
    """Print basic info"""

    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Getting info..."
    results, errors = run_command(args, nodes, "get_versions")

    # Print results
    node_strings = get_node_strings(args, results, justify=False)
    for node in nodes:
        if node in results:
            result = results[node]
            # Get mappings between attributes and formatted strings
            components = COMPONENTS

            print "[ Info from %s ]" % node_strings[node]
            print "Hardware version   : %s" % result.hardware_version
            print "Firmware version   : %s" % result.firmware_version
            # var is the variable, string is the printable string of var
            for var, string in components:
                if hasattr(result, var):
                    version = getattr(result, var)
                    print "%s: %s" % (string.ljust(19), version)
            print

    if not args.quiet and errors:
        print "Some errors occured during the command.\n"

    return len(errors) > 0


def info_ubootenv_command(args):
    """Print uboot info"""
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Getting u-boot environment..."
    results, errors = run_command(args, nodes, "get_ubootenv")

    # Print results
    node_strings = get_node_strings(args, results, justify=False)
    for node in nodes:
        if node in results:
            ubootenv = results[node]
            print "[ U-Boot Environment from %s ]" % node_strings[node]
            for variable in ubootenv.variables:
                print "%s=%s" % (variable, ubootenv.variables[variable])
            print

    if not args.quiet and errors:
        print "Some errors occured during the command.\n"

    return len(errors) > 0
