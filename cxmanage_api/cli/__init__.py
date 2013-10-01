"""Calxeda: __init__.py """


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


import sys
import time

from cxmanage_api.tftp import InternalTftp, ExternalTftp
from cxmanage_api.node import Node
from cxmanage_api.tasks import TaskQueue
from cxmanage_api.cx_exceptions import TftpException


def get_tftp(args):
    """Get a TFTP server"""
    if args.internal_tftp:
        tftp_args = args.internal_tftp.split(':')
        if len(tftp_args) == 1:
            ip_address = tftp_args[0]
            port = 0
        elif len(tftp_args) == 2:
            ip_address = tftp_args[0]
            port = int(tftp_args[1])
        else:
            print ('ERROR: %s is not a valid argument for --internal-tftp'
                    % args.internal_tftp)
            sys.exit(1)
        return InternalTftp(ip_address=ip_address, port=port,
                verbose=args.verbose)

    elif args.external_tftp:
        tftp_args = args.external_tftp.split(':')
        if len(tftp_args) == 1:
            ip_address = tftp_args[0]
            port = 69
        elif len(tftp_args) == 2:
            ip_address = tftp_args[0]
            port = int(tftp_args[1])
        else:
            print ('ERROR: %s is not a valid argument for --external-tftp'
                    % args.external_tftp)
            sys.exit(1)
        return ExternalTftp(ip_address=ip_address, port=port,
                verbose=args.verbose)

    return InternalTftp(verbose=args.verbose)

# pylint: disable=R0912
def get_nodes(args, tftp, verify_prompt=False):
    """Get nodes"""
    hosts = []
    for entry in args.hostname.split(','):
        hosts.extend(parse_host_entry(entry))

    nodes = [Node(ip_address=x, username=args.user, password=args.password,
            tftp=tftp, ecme_tftp_port=args.ecme_tftp_port,
            verbose=args.verbose) for x in hosts]

    if args.all_nodes:
        if not args.quiet:
            print("Getting IP addresses...")

        results, errors = run_command(args, nodes, "get_fabric_ipinfo")

        all_nodes = []
        for node in nodes:
            if node in results:
                for node_id, ip_address in sorted(results[node].iteritems()):
                    new_node = Node(ip_address=ip_address, username=args.user,
                            password=args.password, tftp=tftp,
                            ecme_tftp_port=args.ecme_tftp_port,
                            verbose=args.verbose)
                    new_node.node_id = node_id
                    if not new_node in all_nodes:
                        all_nodes.append(new_node)

        node_strings = get_node_strings(args, all_nodes, justify=False)
        if not args.quiet and all_nodes:
            print("Discovered the following IP addresses:")
            for node in all_nodes:
                print node_strings[node]
            print

        if errors:
            print("ERROR: Failed to get IP addresses. Aborting.\n")
            sys.exit(1)

        if args.nodes:
            if len(all_nodes) != args.nodes:
                print ("ERROR: Discovered %i nodes, expected %i. Aborting.\n"
                        % (len(all_nodes), args.nodes))
                sys.exit(1)
        elif verify_prompt and not args.force:
            print(
                "NOTE: Please check node count! Ensure discovery of all " +
                "nodes in the cluster. Power cycle your system if the " +
                "discovered node count does not equal nodes in " +
                "your system.\n"
            )
            if not prompt_yes("Discovered %i nodes. Continue?"
                    % len(all_nodes)):
                sys.exit(1)

        return all_nodes

    return nodes


def get_node_strings(args, nodes, justify=False):
    """ Get string representations for the nodes. """
    # Use the private _node_id instead of node_id. Strange choice,
    # but we want to avoid accidentally polling the BMC.
    # pylint: disable=W0212
    if args.ids and all(x._node_id != None for x in nodes):
        strings = ["Node %i (%s)" % (x._node_id, x.ip_address) for x in nodes]
    else:
        strings = [x.ip_address for x in nodes]

    if justify:
        just_size = max(16, max(len(x) for x in strings) + 1)
        strings = [x.ljust(just_size) for x in strings]

    return dict(zip(nodes, strings))


# pylint: disable=R0915
def run_command(args, nodes, name, *method_args):
    """Runs a command on nodes."""
    if args.threads != None:
        task_queue = TaskQueue(threads=args.threads, delay=args.command_delay)
    else:
        task_queue = TaskQueue(delay=args.command_delay)

    tasks = {}
    for node in nodes:
        tasks[node] = task_queue.put(getattr(node, name), *method_args)

    results = {}
    errors = {}
    try:
        counter = 0
        while any(x.is_alive() for x in tasks.values()):
            if not args.quiet:
                _print_command_status(tasks, counter)
                counter += 1
            time.sleep(0.25)

        for node, task in tasks.iteritems():
            if task.status == "Completed":
                results[node] = task.result
            else:
                errors[node] = task.error

    except KeyboardInterrupt:
        args.retry = 0

        for node, task in tasks.iteritems():
            if task.status == "Completed":
                results[node] = task.result
            elif task.status == "Failed":
                errors[node] = task.error
            else:
                errors[node] = KeyboardInterrupt(
                    "Aborted by keyboard interrupt"
                )

    if not args.quiet:
        _print_command_status(tasks, counter)
        print("\n")

    # Handle errors
    should_retry = False
    if errors:
        _print_errors(args, nodes, errors)
        if args.retry == None:
            sys.stdout.write("Retry command on failed hosts? (y/n): ")
            sys.stdout.flush()
            while True:
                command = raw_input().strip().lower()
                if command in ['y', 'yes']:
                    should_retry = True
                    break
                elif command in ['n', 'no']:
                    print
                    break
        elif args.retry >= 1:
            should_retry = True
            if args.retry == 1:
                print("Retrying command 1 more time...")
            elif args.retry > 1:
                print("Retrying command %i more times..." % args.retry)
            args.retry -= 1

    if should_retry:
        nodes = [x for x in nodes if x in errors]
        new_results, errors = run_command(args, nodes, name, *method_args)
        results.update(new_results)

    return results, errors


def prompt_yes(prompt):
    """Prompts the user. """
    sys.stdout.write("%s (y/n) " % prompt)
    sys.stdout.flush()
    while True:
        command = raw_input().strip().lower()
        if command in ['y', 'yes']:
            print
            return True
        elif command in ['n', 'no']:
            print
            return False


def parse_host_entry(entry, hostfiles=None):
    """parse a host entry"""
    if not(hostfiles):
        hostfiles = set()

    try:
        return parse_hostfile_entry(entry, hostfiles)
    except ValueError:
        try:
            return parse_ip_range_entry(entry)
        except ValueError:
            return [entry]


def parse_hostfile_entry(entry, hostfiles=None):
    """parse a hostfile entry, returning a list of hosts"""
    if not(hostfiles):
        hostfiles = set()

    if entry.startswith('file='):
        filename = entry[5:]
    elif entry.startswith('hostfile='):
        filename = entry[9:]
    else:
        raise ValueError('%s is not a hostfile entry' % entry)

    if filename in hostfiles:
        return []
    hostfiles.add(filename)

    entries = []
    try:
        for line in open(filename):
            for element in line.partition('#')[0].split():
                for hostfile_entry in element.split(','):
                    entries.extend(parse_host_entry(hostfile_entry, hostfiles))
    except IOError:
        print 'ERROR: %s is not a valid hostfile entry' % entry
        sys.exit(1)

    return entries


def parse_ip_range_entry(entry):
    """ Get a list of ip addresses in a given range"""
    try:
        start, end = entry.split('-')

        # Convert start address to int
        start_bytes = [int(x) for x in start.split('.')]

        start_i = ((start_bytes[0] << 24) | (start_bytes[1] << 16)
                | (start_bytes[2] << 8) | (start_bytes[3]))

        # Convert end address to int
        end_bytes = [int(x) for x in end.split('.')]
        end_i = ((end_bytes[0] << 24) | (end_bytes[1] << 16)
                | (end_bytes[2] << 8) | (end_bytes[3]))

        # Get ip addresses in range
        addresses = []
        for i in range(start_i, end_i + 1):
            address_bytes = [(i >> (24 - 8 * x)) & 0xff for x in range(4)]
            addresses.append('%i.%i.%i.%i' % tuple(address_bytes))

    except (ValueError, IndexError):
        raise ValueError('%s is not an IP range' % entry)

    return addresses


def _print_errors(args, nodes, errors):
    """ Print errors if they occured """
    if errors:
        node_strings = get_node_strings(args, nodes, justify=True)
        print("Command failed on these hosts")
        for node in nodes:
            if node in errors:
                print("%s: %s" % (node_strings[node], errors[node]))
        print

        # Print a special message for TFTP errors
        if all(isinstance(x, TftpException) for x in errors.itervalues()):
            print(
                "There may be networking issues (when behind NAT) between " +
                "the host (where cxmanage is running) and the Calxeda node " +
                "when establishing a TFTP session. Please refer to the " +
                "documentation for more information.\n"
            )


def _print_command_status(tasks, counter):
    """ Print the status of a command """
    message = "\r%i successes  |  %i errors  |  %i nodes left  |  %s"
    successes = len([x for x in tasks.values() if x.status == "Completed"])
    errors = len([x for x in tasks.values() if x.status == "Failed"])
    nodes_left = len(tasks) - successes - errors
    dots = "".join(["." for x in range(counter % 4)]).ljust(3)
    sys.stdout.write(message % (successes, errors, nodes_left, dots))
    sys.stdout.flush()


# These are needed for ipinfo and whenever version information is printed
COMPONENTS = [
    ("ecme_version", "ECME version"),
    ("cdb_version", "CDB version"),
    ("stage2_version", "Stage2boot version"),
    ("bootlog_version", "Bootlog version"),
    ("a9boot_version", "A9boot version"),
    ("a15boot_version", "A15boot version"),
    ("uboot_version", "Uboot version"),
    ("ubootenv_version", "Ubootenv version"),
    ("dtb_version", "DTB version"),
]

