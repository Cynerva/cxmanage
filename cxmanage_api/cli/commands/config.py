"""Calxeda: config.py  """


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


from cxmanage_api.cli import get_tftp, get_nodes, get_node_strings, run_command

from cxmanage_api.ubootenv import validate_boot_args, \
        validate_pxe_interface


def config_reset_command(args):
    """reset to factory default settings"""
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp, verify_prompt=True)

    if not args.quiet:
        print "Sending config reset command..."

    _, errors = run_command(args, nodes, "config_reset")

    if not args.quiet and not errors:
        print "Command completed successfully.\n"

    return len(errors) > 0


def config_boot_command(args):
    """set A9 boot order"""
    if args.boot_order == ['status']:
        return config_boot_status_command(args)

    validate_boot_args(args.boot_order)

    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Setting boot order..."

    _, errors = run_command(args, nodes, "set_boot_order",
            args.boot_order)

    if not args.quiet and not errors:
        print "Command completed successfully.\n"

    return len(errors) > 0


def config_boot_status_command(args):
    """Get boot status command."""
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Getting boot order..."
    results, errors = run_command(args, nodes, "get_boot_order")

    # Print results
    if results:
        node_strings = get_node_strings(args, results, justify=True)
        print "Boot order"
        for node in nodes:
            if node in results:
                print "%s: %s" % (node_strings[node], ",".join(results[node]))
        print

    if not args.quiet and errors:
        print "Some errors occured during the command.\n"

    return len(errors) > 0


def config_pxe_command(args):
    """set the PXE boot interface"""
    if args.interface == "status":
        return config_pxe_status_command(args)

    validate_pxe_interface(args.interface)

    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Setting pxe interface..."

    _, errors = run_command(args, nodes, "set_pxe_interface",
            args.interface)

    if not args.quiet and not errors:
        print "Command completed successfully.\n"

    return len(errors) > 0


def config_pxe_status_command(args):
    """Gets pxe status."""
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Getting pxe interface..."
    results, errors = run_command(args, nodes, "get_pxe_interface")

    # Print results
    if results:
        node_strings = get_node_strings(args, results, justify=True)
        print "PXE interface"
        for node in nodes:
            if node in results:
                print "%s: %s" % (node_strings[node], results[node])
        print

    if not args.quiet and errors:
        print "Some errors occured during the command.\n"

    return len(errors) > 0
