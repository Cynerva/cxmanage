"""Calxeda: ubootenv.py """

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


import struct

from cxmanage_api.simg import has_simg, get_simg_contents
from cxmanage_api.crc32 import get_crc32
from cxmanage_api.cx_exceptions import UbootenvError


ENVIRONMENT_SIZE = 8192
UBOOTENV_V1_VARIABLES = ["bootcmd_default", "bootcmd_sata", "bootcmd_pxe",
        "bootdevice"]
UBOOTENV_V2_VARIABLES = ["bootcmd0", "init_scsi", "bootcmd_scsi", "init_pxe",
        "bootcmd_pxe", "devnum"]


class UbootEnv(object):
    """Represents a U-Boot Environment.

    >>> from cxmanage_api.ubootenv import UbootEnv
    >>> uboot = UbootEnv()

    :param contents: UBootEnvironment contnents.
    :type contents: string

    """

    def __init__(self, contents=None):
        """Default constructor for the UbootEnv class."""
        self.variables = {}

        if (contents != None):
            if (has_simg(contents)):
                contents = get_simg_contents(contents)

            contents = contents.rstrip("%c%c" % (chr(0), chr(255)))[4:]
            lines = contents.split(chr(0))
            for line in lines:
                part = line.partition("=")
                self.variables[part[0]] = part[2]

    # pylint: disable=R0912
    def set_boot_order(self, boot_args):
        """Sets the boot order specified in the uboot environment.

        >>> uboot.set_boot_order(boot_args=['disk', 'pxe'])

        .. note::
            * Valid Args:
                             pxe     - boot from pxe server\n
                             disk    - boot from default sata device\n
                             diskX   - boot from sata device X\n
                             diskX:Y - boot from sata device X, partition Y\n
                             retry   - retry last boot device indefinitely\n
                             reset   - reset A9\n

        :param boot_args: Boot args (boot order). A list of strings.
        :type boot_args: list

        :raises ValueError: If an invalid boot device is specified.
        :raises ValueError: If 'retry' and 'reset' args are used together.
        :raises UbootenvError: If the u-boot environment is unrecognized

        """
        validate_boot_args(boot_args)
        if boot_args == self.get_boot_order():
            return

        commands = []
        retry = False
        reset = False

        if all(x in self.variables for x in UBOOTENV_V1_VARIABLES):
            version = 1
        elif all(x in self.variables for x in UBOOTENV_V2_VARIABLES):
            version = 2
        else:
            raise UbootenvError("Unrecognized u-boot environment")

        for arg in boot_args:
            if arg == "retry":
                retry = True
            elif arg == "reset":
                reset = True
            elif version == 1:
                if arg == "pxe":
                    commands.append("run bootcmd_pxe")
                elif arg == "disk":
                    commands.append("run bootcmd_sata")
                elif arg.startswith("disk"):
                    try:
                        # pylint: disable=W0141
                        dev, part = map(int, arg[4:].split(":"))
                        bootdevice = "%i:%i" % (dev, part)
                    except ValueError:
                        bootdevice = str(int(arg[4:]))
                    commands.append("setenv bootdevice %s && run bootcmd_sata"
                            % bootdevice)
            elif version == 2:
                if arg == "pxe":
                    commands.append("run init_pxe && run bootcmd_pxe")
                elif arg == "disk":
                    commands.append("run init_scsi && run bootcmd_scsi")
                elif arg.startswith("disk"):
                    try:
                        # pylint: disable=W0141
                        dev, part = map(int, arg[4:].split(":"))
                        bootdevice = "%i:%i" % (dev, part)
                    except ValueError:
                        bootdevice = str(int(arg[4:]))
                    commands.append(
                        "setenv devnum %s && run init_scsi && run bootcmd_scsi"
                        % bootdevice
                    )

        if retry and reset:
            raise ValueError("retry and reset are mutually exclusive")
        elif retry:
            commands[-1] = "while true\ndo\n%s\nsleep 1\ndone" % commands[-1]
        elif reset:
            commands.append("reset")

        if version == 1:
            self.variables["bootcmd_default"] = "; ".join(commands)
        else:
            self.variables["bootcmd0"] = "; ".join(commands)

    def get_boot_order(self):
        """Gets the boot order specified in the uboot environment.

        >>> uboot.get_boot_order()
        ['disk', 'pxe']

        :returns: Boot order for this U-Boot Environment.
        :rtype: string

        :raises UbootenvError: If a boot command is unrecognized.

        """
        boot_args = []

        if self.variables["bootcmd0"] == "run boot_iter":
            for target in self.variables["boot_targets"].split():
                if target == "pxe":
                    boot_args.append("pxe")
                elif target == "scsi":
                    boot_args.append("disk")
                else:
                    raise UbootenvError("Unrecognized boot target: %s"
                            % target)
        else:
            if "bootcmd_default" in self.variables:
                commands = self.variables["bootcmd_default"].split("; ")
            else:
                commands = self.variables["bootcmd0"].split("; ")

            retry = False
            for command in commands:
                if command.startswith("while true"):
                    retry = True
                    command = command.split("\n")[2]

                if command in ["run bootcmd_pxe",
                        "run init_pxe && run bootcmd_pxe"]:
                    boot_args.append("pxe")
                elif command in ["run bootcmd_sata",
                        "run init_scsi && run bootcmd_scsi"]:
                    boot_args.append("disk")
                elif (command.startswith("setenv bootdevice") or
                        command.startswith("setenv devnum")):
                    boot_args.append("disk%s" % command.split()[2])
                elif (command == "reset"):
                    boot_args.append("reset")
                    break
                else:
                    raise UbootenvError("Unrecognized boot command: %s"
                            % command)

                if retry:
                    boot_args.append("retry")
                    break

        if not boot_args:
            boot_args = ["none"]

        validate_boot_args(boot_args)  # sanity check
        return boot_args


    def set_pxe_interface(self, interface):
        """Sets the interfacespecified in the uboot environment.

        >>> uboot.set_pxe_interface('eth0')

        .. note::
            * Valid Args: eth0 or eth1

        :param interface: The interface to set.
        :type boot_args: string

        :raises ValueError: If an invalid interface is specified.

        """
        validate_pxe_interface(interface)
        if interface == self.get_pxe_interface():
            return

        if interface == "eth0":
            self.variables["ethprime"] = "xgmac0"
        elif (interface == "eth1"):
            self.variables["ethprime"] = "xgmac1"
        else:
            raise ValueError("Invalid pxe interface: %s" % interface)

    def get_pxe_interface(self):
        """Returns a string representation of the pxe interface.

        >>> uboot.get_pxe_interface()
        'eth0'

        :returns: Boot order for this U-Boot Environment.
        :rtype: string
        :raises ValueError: If the u-boot environment value is not recognized.

        """

        # This is based on reading the ethprime environment variable, and
        # translating from xgmacX to ethX. By default ethprime is not set
        # and eth0 is the assumed default (NOTE: this is brittle)

        if "ethprime" in self.variables:
            xgmac = self.variables["ethprime"]
            if xgmac == "xgmac0":
                return "eth0"
            elif (xgmac == "xgmac1"):
                return "eth1"
            else:
                raise ValueError("Unrecognized value for ethprime")
        else:
            return "eth0"


    def get_contents(self):
        """Returns a raw string representation of the uboot environment.

        >>> uboot.get_contents()
        'j4\x88\xb7bootcmd_default=run bootcmd_sata; run bootcmd_pxe ... '
        >>> #
        >>> # Output trimmed for brevity ...
        >>> #

        :returns: Raw string representation of the UBoot Environment.
        :rtype: string

        """
        contents = ""
        # Add variables
        for variable in self.variables:
            contents += "%s=%s\0" % (variable, self.variables[variable])
        contents += "\0"
        # Add padding to end
        contents += "".join([chr(255)
                for _ in range(ENVIRONMENT_SIZE - len(contents) - 4)])
        # Add crc32 to beginning
        crc32 = get_crc32(contents, 0xFFFFFFFF) ^ 0xFFFFFFFF
        contents = struct.pack("<I", crc32) + contents
        return contents


def validate_boot_args(boot_args):
    """ Validate boot arguments. Raises a ValueError if the args are invalid."""
    for arg in boot_args:
        if arg in ["retry", "reset", "pxe", "disk", "none"]:
            continue
        elif arg.startswith("disk"):
            try:
                # pylint: disable=W0141
                map(int, arg[4:].split(":"))
            except ValueError:
                try:
                    int(arg[4:])
                except ValueError:
                    raise ValueError("Invalid boot arg: %s" % arg)
        else:
            raise ValueError("Invalid boot arg: %s" % arg)


def validate_pxe_interface(interface):
    """ Validate pxe interface. Raises a ValueError if the args are invalid."""
    if not interface in ["eth0", "eth1"]:
        raise ValueError("Invalid pxe interface: %s" % interface)
