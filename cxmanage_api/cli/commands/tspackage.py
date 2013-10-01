"""Calxeda: tspackage.py"""


# Copyright 2013 Calxeda, Inc.
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


#
# A cxmanage command to collect information about a node and archive it.
#
# Example:
# cxmanage tspackage 10.10.10.10
#


import os
import time
import shutil
import tarfile
import tempfile

from cxmanage_api.cli import get_tftp, get_nodes, run_command, COMPONENTS


def tspackage_command(args):
    """Get information pertaining to each node.
    This includes:
    Version info (like cxmanage info)
    MAC addresses
    Sensor readings
    Sensor data records
    Firmware info
    Boot order
    SELs (System Event Logs),
    Depth charts
    Routing Tables

    This data will be written to a set of files. Each node will get its own
    file. All of these files will be archived and saved to the user's current
    directory.

    Internally, this command is called from:
    ~/virtual_testenv/workspace/cx_manage_util/scripts/cxmanage

    """
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    # Make a temporary directory to store the node information files
    original_dir = os.getcwd()
    temp_dir = tempfile.mkdtemp()
    os.chdir(temp_dir)
    tspackage_dir = "tspackage.%s" % time.strftime("%Y%m%d%H%M%S")
    os.mkdir(tspackage_dir)
    os.chdir(tspackage_dir)

    quiet = args.quiet

    if not quiet:
        print("Getting version information...")
    write_version_info(args, nodes)

    if not quiet:
        print("Getting node FRU version...")
    write_node_fru_version(args, nodes)

    if not quiet:
        print("Getting slot FRU version...")
    write_slot_fru_version(args, nodes)

    if not quiet:
        print("Getting boot order...")
    write_boot_order(args, nodes)

    if not quiet:
        print("Getting MAC addresses...")
    write_mac_addrs(args, nodes)

    if not quiet:
        print("Getting sensor information...")
    write_sensor_info(args, nodes)

    if not quiet:
        print("Getting firmware information...")
    write_fwinfo(args, nodes)

    if not quiet:
        print("Getting system event logs...")
    write_sel(args, nodes)

    if not quiet:
        print("Getting depth charts...")
    write_depth_chart(args, nodes)

    if not quiet:
        print("Getting routing tables...")
    write_routing_table(args, nodes)

    # Archive the files
    archive(os.getcwd(), original_dir)

    # The original files are already archived, so we can delete them.
    shutil.rmtree(temp_dir)


def write_version_info(args, nodes):
    """Write the version info (like cxmanage info) for each node
    to their respective files.

    """
    info_results, _ = run_command(args, nodes, "get_versions")


    for node in nodes:
        lines = []  # The lines of text to write to file

        # Since this is the first line of the file, we don't need a \n
        write_to_file(
            node,
            "[ Version Info for Node %d ]" % node.node_id,
            add_newlines=False
        )

        lines.append("ECME IP Address    : %s" % node.ip_address)

        if node in info_results:
            info_result = info_results[node]
            lines.append(
                "Hardware version   : %s" %
                info_result.hardware_version
            )
            lines.append(
                "Firmware version   : %s" %
                info_result.firmware_version
            )

            # Get mappings between attributes and formatted strings
            components = COMPONENTS
            for var, description in components:
                if hasattr(info_result, var):
                    version = getattr(info_result, var)
                    lines.append("%s: %s" % (description.ljust(19), version))
        else:
            lines.append("No version information could be found.")

        write_to_file(node, lines)

def write_node_fru_version(args, nodes):
    """Write the node and slot FRU versions for each node to their
    respective files.

    """
    node_fru_results, _ = run_command(args, nodes, "get_node_fru_version")

    for node in nodes:
        lines = []  # Lines of text to write to file
        if node in node_fru_results:
            lines.append("%s: %s" % \
                ("Node FRU Version".ljust(19), node_fru_results[node]))
        else:
            lines.append("\nWARNING: No node FRU found!")
        write_to_file(node, lines)

def write_slot_fru_version(args, nodes):
    """Write the node and slot FRU versions for each node to their
    respective files.

    """
    slot_fru_results, _ = run_command(args, nodes, "get_slot_fru_version")

    for node in nodes:
        lines = []  # Lines of text to write to file
        if node in slot_fru_results:
            lines.append("%s: %s" % \
                ("Slot FRU Version".ljust(19), slot_fru_results[node]))
        else:
            lines.append("Error reading slot FRU. Perhaps the system board " +
                         "does not have slot FRUs?")

        write_to_file(node, lines)

def write_mac_addrs(args, nodes):
    """Write the MAC addresses for each node to their respective files."""
    mac_addr_results, _ = run_command(
        args,
        nodes,
        "get_fabric_macaddrs"
    )

    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ MAC Addresses for Node %d ]" % node.node_id)

        if node in mac_addr_results:
            for port in mac_addr_results[node][node.node_id]:
                for mac_address in mac_addr_results[node][node.node_id][port]:
                    lines.append(
                        "Node %i, Port %i: %s" %
                        (node.node_id, port, mac_address)
                    )
        else:
            lines.append("\nWARNING: No MAC addresses found!")

        write_to_file(node, lines)

# pylint: disable=R0914
def write_sensor_info(args, nodes):
    """Write sensor information for each node to their respective files."""
    args.sensor_name = ""

    results, _ = run_command(args, nodes, "get_sensors",
                             args.sensor_name)

    sensors = {}
    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ Sensors for Node %d ]" % node.node_id)

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
        else:
            print("Could not get sensor info!")
            lines.append("Could not get sensor info!")

        for sensor_name, readings in sensors.iteritems():
            for reading_node, reading, suffix in readings:
                if reading_node.ip_address == node.ip_address:
                    left_side = "{:<18}".format(sensor_name)
                    right_side = ": %.2f %s" % (reading, suffix)
                    lines.append(left_side + right_side)

        write_to_file(node, lines)


def write_fwinfo(args, nodes):
    """Write information about each node's firware partitions
    to its respective file.

    """
    results, _ = run_command(args, nodes, "get_firmware_info")

    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ Firmware Info for Node %d ]" % node.node_id)

        if node in results:
            first_partition = True  # The first partiton doesn't need \n

            for partition in results[node]:
                if first_partition:
                    lines.append("Partition : %s" % partition.partition)
                    first_partition = False
                else:
                    lines.append("\nPartition : %s" % partition.partition)
                lines.append("Type      : %s" % partition.type)
                lines.append("Offset    : %s" % partition.offset)
                lines.append("Size      : %s" % partition.size)
                lines.append("Priority  : %s" % partition.priority)
                lines.append("Daddr     : %s" % partition.daddr)
                lines.append("Flags     : %s" % partition.flags)
                lines.append("Version   : %s" % partition.version)
                lines.append("In Use    : %s" % partition.in_use)
        else:
            lines.append("Could not get firmware info!")
        write_to_file(node, lines)


def write_boot_order(args, nodes):
    """Write the boot order of each node to their respective files."""
    results, _ = run_command(args, nodes, "get_boot_order")

    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ Boot Order for Node %d ]" % node.node_id)

        if node in results:
            lines.append(", ".join(results[node]))
        else:
            lines.append("Could not get boot order!")

        write_to_file(node, lines)


def write_sel(args, nodes):
    """Write the SEL for each node to their respective files."""
    results, _ = run_command(args, nodes, "get_sel")

    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ System Event Log for Node %d ]" % node.node_id)

        try:
            if node in results:
                for event in results[node]:
                    lines.append(event)

        # pylint: disable=W0703
        except Exception as error:
            lines.append("Could not get SEL! " + str(error))
            if not args.quiet:
                print("Failed to get system event log for " + node.ip_address)

        write_to_file(node, lines)


def write_depth_chart(args, nodes):
    """Write the depth chart for each node to their respective files."""
    depth_results, _ = run_command(args, nodes, "get_depth_chart")

    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ Depth Chart for Node %d ]" % node.node_id)

        if node in depth_results:
            depth_chart = depth_results[node]
            for key in depth_chart:
                subchart = depth_chart[key]
                lines.append("To node " + str(key))

                # The 'shortest' entry is one tuple, but
                # the 'others' are a list.
                for subkey in subchart:
                    if str(subkey) == "shortest":
                        lines.append(
                            "  " + str(subkey) +
                            " : " + str(subchart[subkey])
                        )
                    else:
                        for entry in subchart[subkey]:
                            lines.append(
                                "  " + str(subkey) +
                                "   : " + str(entry)
                            )

        else:
            lines.append("Could not get depth chart!")

        write_to_file(node, lines)


def write_routing_table(args, nodes):
    """Write the routing table for each node to their respective files."""
    routing_results, _ = run_command(args, nodes, "get_routing_table")

    for node in nodes:
        lines = []  # Lines of text to write to file
        # \n is used here to give a blank line before this section
        lines.append("\n[ Routing Table for Node %d ]" % node.node_id)

        if node in routing_results:
            table = routing_results[node]
            for node_to in table:
                lines.append(str(node_to) + " : " + str(table[node_to]))
        else:
            lines.append("Could not get routing table!")

        write_to_file(node, lines)


def write_to_file(node, to_write, add_newlines=True):
    """Append to_write to an info file for every node in nodes.

    :param node: Node object to write about
    :type node: Node object
    :param to_write: Text to write to the files
    :type to_write: List of strings
    :param add_newlines: Whether to add newline characters before
    every item in to_write. True by default. True will add newline
    characters.
    :type add_newlines: bool

    """
    with open("node" + str(node.node_id) + ".txt", 'a') as node_file:
        if add_newlines:
            # join() doesn't add a newline before the first item
            to_write[0] = "\n" + to_write[0]
            node_file.write("\n".join(to_write))
        else:
            node_file.write("".join(to_write))


def archive(directory_to_archive, destination):
    """Creates a .tar containing everything in the directory_to_archive.
    The .tar is saved to destination with the same name as the original
    directory_to_archive, but with .tar appended.

    :param directory_to_archive: A path to the directory to be archived.
    :type directory_to_archive: string

    :param destination: A path to the location the .tar should be saved
    :type destination: string

    """
    os.chdir(os.path.dirname(directory_to_archive))

    tar_name = os.path.basename(directory_to_archive) + ".tar"
    tar_name = os.path.join(destination, tar_name)

    with tarfile.open(tar_name, "w") as tar:
        tar.add(os.path.basename(directory_to_archive))

    print(
        "Finished! One archive created:\n" +
        os.path.join(destination, tar_name)
    )
