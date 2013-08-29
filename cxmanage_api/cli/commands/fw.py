"""Calxeda: fw.py """

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


from pkg_resources import parse_version

from cxmanage_api.cli import get_tftp, get_nodes, get_node_strings, \
        run_command, prompt_yes

from cxmanage_api.image import Image
from cxmanage_api.firmware_package import FirmwarePackage

# pylint: disable=R0912
def fwupdate_command(args):
    """update firmware on a cluster or host"""
    def do_update():
        """ Do a single firmware check+update. Returns True on failure. """
        if not args.force:
            if not args.quiet:
                print "Checking hosts..."

            _, errors = run_command(args, nodes, "_check_firmware",
                    package, args.partition, args.priority)
            if errors:
                print "ERROR: Firmware update aborted."
                return True

        if not args.quiet:
            print "Updating firmware..."

        _, errors = run_command(args, nodes, "update_firmware", package,
            args.partition, args.priority)
        if errors:
            print "ERROR: Firmware update failed."
            return True

        return False

    def do_reset():
        """ Reset and wait. Returns True on failure. """
        if not args.quiet:
            print "Checking ECME versions..."

        results, errors = run_command(args, nodes, "get_versions")
        if errors:
            print "ERROR: MC reset aborted. Backup partitions not updated."
            return True

        for result in results.values():
            version = result.ecme_version.lstrip("v")
            if parse_version(version) < parse_version("1.2.0"):
                print "ERROR: MC reset is unsafe on ECME version v%s" % version
                print "Please power cycle the system and start a new fwupdate."
                return True

        if not args.quiet:
            print "Resetting nodes..."

        results, errors = run_command(args, nodes, "mc_reset", True)
        if errors:
            print "ERROR: MC reset failed. Backup partitions not updated."
            return True

        return False

    if args.image_type == "PACKAGE":
        package = FirmwarePackage(args.filename)
    else:
        try:
            simg = None
            if args.force_simg:
                simg = False
            elif args.skip_simg:
                simg = True

            image = Image(args.filename, args.image_type, simg, args.daddr,
                    args.skip_crc32, args.fw_version)
            package = FirmwarePackage()
            package.images.append(image)
        except ValueError as err:
            print "ERROR: %s" % err
            return True

    if not args.all_nodes:
        if args.force:
            print(
                'WARNING: Updating firmware without --all-nodes' +
                ' is dangerous.'
            )
        else:
            if not prompt_yes(
                'WARNING: Updating firmware without ' +
                '--all-nodes is dangerous. Continue?'
                ):
                return 1

    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp, verify_prompt=True)

    errors = do_update()

    if args.full and not errors:
        errors = do_reset()
        if not errors:
            errors = do_update()

    if not args.quiet and not errors:
        print "Command completed successfully.\n"

    return errors


def fwinfo_command(args):
    """print firmware info"""
    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp)

    if not args.quiet:
        print "Getting firmware info..."

    results, errors = run_command(args, nodes, "get_firmware_info")

    node_strings = get_node_strings(args, results, justify=False)
    for node in nodes:
        if node in results:
            print "[ Firmware info for %s ]" % node_strings[node]

            for partition in results[node]:
                print "Partition : %s" % partition.partition
                print "Type      : %s" % partition.type
                print "Offset    : %s" % partition.offset
                print "Size      : %s" % partition.size
                print "Priority  : %s" % partition.priority
                print "Daddr     : %s" % partition.daddr
                print "Flags     : %s" % partition.flags
                print "Version   : %s" % partition.version
                print "In Use    : %s" % partition.in_use
                print

    if not args.quiet and errors:
        print "Some errors occured during the command.\n"

    return len(errors) > 0
