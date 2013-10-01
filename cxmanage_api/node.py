# pylint: disable=C0302
"""Calxeda: node.py"""


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

import os
import re
import time
import tempfile
import subprocess

from pkg_resources import parse_version
from pyipmi import make_bmc, IpmiError
from pyipmi.bmc import LanBMC as BMC
from tftpy.TftpShared import TftpException

from cxmanage_api import loggers
from cxmanage_api import temp_file
from cxmanage_api.tftp import InternalTftp, ExternalTftp
from cxmanage_api.image import Image as IMAGE
from cxmanage_api.ubootenv import UbootEnv as UBOOTENV
from cxmanage_api.ip_retriever import IPRetriever as IPRETRIEVER
from cxmanage_api.cx_exceptions import TimeoutError, NoSensorError, \
        SocmanVersionError, FirmwareConfigError, PriorityIncrementError, \
        NoPartitionError, TransferFailure, ImageSizeError, \
        PartitionInUseError, UbootenvError, NoFRUVersionError, \
        EEPROMUpdateError


# pylint: disable=R0902, R0904
class Node(object):
    """A node is a single instance of an ECME.

    >>> # Typical usage ...
    >>> from cxmanage_api.node import Node
    >>> node = Node(ip_adress='10.20.1.9', verbose=True)

    :param ip_address: The ip_address of the Node.
    :type ip_address: string
    :param username: The login username credential. [Default admin]
    :type username: string
    :param password: The login password credential. [Default admin]
    :type password: string
    :param tftp: The internal/external TFTP server to use for data xfer.
    :type tftp: `Tftp <tftp.html>`_
    :param verbose: Flag to turn on verbose output (cmd/response).
    :type verbose: boolean
    :param bmc: BMC object for this Node. Default: pyipmi.bmc.LanBMC
    :type bmc: BMC
    :param image: Image object for this node. Default cxmanage_api.Image
    :type image: `Image <image.html>`_
    :param ubootenv: UbootEnv  for this node. Default cxmanage_api.UbootEnv
    :type ubootenv: `UbootEnv <ubootenv.html>`_

    """
    # pylint: disable=R0913
    def __init__(self, ip_address, username="admin", password="admin",
                  tftp=None, ecme_tftp_port=5001, verbose=False, bmc=None,
                  image=None, ubootenv=None, ipretriever=None):
        """Default constructor for the Node class."""
        if (not tftp):
            tftp = InternalTftp.default()

        # Dependency Integration
        if (not bmc):
            bmc = BMC
        if (not image):
            image = IMAGE
        if (not ubootenv):
            ubootenv = UBOOTENV
        if (not ipretriever):
            ipretriever = IPRETRIEVER

        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.tftp = tftp
        self.ecme_tftp = ExternalTftp(ip_address, ecme_tftp_port)
        self.verbose = verbose

        self.bmc = make_bmc(bmc, hostname=ip_address, username=username,
                            password=password, verbose=verbose)
        self.image = image
        self.ubootenv = ubootenv
        self.ipretriever = ipretriever

        self._node_id = None

    def __eq__(self, other):
        return isinstance(other, Node) and self.ip_address == other.ip_address

    def __hash__(self):
        return hash(self.ip_address)

    def __str__(self):
        return 'Node: %s' % self.ip_address

    @property
    def tftp_address(self):
        """Returns the tftp_address (ip:port) that this node is using.

        >>> node.tftp_address
        '10.20.2.172:35123'

        :returns: The tftp address and port that this node is using.
        :rtype: string

        """
        return '%s:%s' % (self.tftp.get_address(relative_host=self.ip_address),
                          self.tftp.port)

    @property
    def node_id(self):
        """ Returns the numerical ID for this node.

        >>> node.node_id
        0

        :returns: The ID of this node.
        :rtype: integer

        """
        if self._node_id == None:
            self._node_id = self.bmc.fabric_get_node_id()
        return self._node_id

    @node_id.setter
    def node_id(self, value):
        """ Sets the ID for this node.

        :param value: The value we want to set.
        :type value: integer

        """
        self._node_id = value

    def get_mac_addresses(self):
        """Gets a dictionary of MAC addresses for this node. The dictionary
        maps each port/interface to a list of MAC addresses for that interface.

        >>> node.get_mac_addresses()
        {
         0: ['fc:2f:40:3b:ec:40'],
         1: ['fc:2f:40:3b:ec:41'],
         2: ['fc:2f:40:3b:ec:42']
        }

        :return: MAC Addresses for all interfaces.
        :rtype: dictionary

        """
        return self.get_fabric_macaddrs()[self.node_id]

    def add_macaddr(self, iface, macaddr):
        """Add mac address on an interface

        >>> node.add_macaddr(iface, macaddr)

        :param iface: Interface to add to
        :type iface: integer
        :param macaddr: MAC address to add
        :type macaddr: string

        :raises IpmiError: If errors in the command occur with BMC \
communication.

        """
        self.bmc.fabric_add_macaddr(iface=iface, macaddr=macaddr)

    def rm_macaddr(self, iface, macaddr):
        """Remove mac address from an interface

        >>> node.rm_macaddr(iface, macaddr)

        :param iface: Interface to remove from
        :type iface: integer
        :param macaddr: MAC address to remove
        :type macaddr: string

        :raises IpmiError: If errors in the command occur with BMC \
communication.

        """
        self.bmc.fabric_rm_macaddr(iface=iface, macaddr=macaddr)

    def get_power(self):
        """Returns the power status for this node.

        >>> # Powered ON system ...
        >>> node.get_power()
        True
        >>> # Powered OFF system ...
        >>> node.get_power()
        False

        :return: The power state of the Node.
        :rtype: boolean

        """
        return self.bmc.get_chassis_status().power_on

    def set_power(self, mode, ignore_existing_state=False):
        """Send an IPMI power command to this target.

        >>> # To turn the power 'off'
        >>> node.set_power(mode='off')
        >>> # A quick 'get' to see if it took effect ...
        >>> node.get_power()
        False

        >>> # To turn the power 'on'
        >>> node.set_power(mode='on')

        :param mode: Mode to set the power state to. ('on'/'off')
        :type mode: string
        :param ignore_existing_state: Flag that allows the caller to only try
                                      to turn on or off the node if it is not
                                      turned on or off, respectively.
        :type ignore_existing_state: boolean

        """
        if ignore_existing_state:
            if self.get_power() and mode == "on":
                return
            if not self.get_power() and mode == "off":
                return
        self.bmc.set_chassis_power(mode=mode)

    def get_power_policy(self):
        """Return power status reported by IPMI.

        >>> node.get_power_policy()
        'always-off'

        :return: The Nodes current power policy.
        :rtype: string

        :raises IpmiError: If errors in the command occur with BMC \
communication.

        """
        return self.bmc.get_chassis_status().power_restore_policy

    def set_power_policy(self, state):
        """Set default power state for Linux side.

        >>> # Set the state to 'always-on'
        >>> node.set_power_policy(state='always-on')
        >>> # A quick check to make sure our setting took ...
        >>> node.get_power_policy()
        'always-on'

        :param state: State to set the power policy to.
        :type state: string

        """
        self.bmc.set_chassis_policy(state)

    def mc_reset(self, wait=False):
        """Sends a Master Control reset command to the node.

        >>> node.mc_reset()

        :param wait: Wait for the node to come back up.
        :type wait: boolean

        :raises Exception: If the BMC command contains errors.
        :raises IPMIError: If there is an IPMI error communicating with the BMC.

        """
        self.bmc.mc_reset("cold")

        if wait:
            deadline = time.time() + 300.0

            # Wait for it to go down...
            time.sleep(60)

            # Now wait to come back up!
            while time.time() < deadline:
                time.sleep(1)
                try:
                    self.bmc.get_info_basic()
                    break
                except IpmiError:
                    pass
            else:
                raise Exception("Reset timed out")

    def get_sel(self):
        """Get the system event log for this node.

        >>> node.get_sel()
        ['1 | 06/21/2013 | 16:13:31 | System Event #0xf4 |',
         '0 | 06/27/2013 | 20:25:18 | System Boot Initiated #0xf1 | \
Initiated by power up | Asserted',
         '1 | 06/27/2013 | 20:25:35 | Watchdog 2 #0xfd | Hard reset | \
Asserted',
         '2 | 06/27/2013 | 20:25:18 | System Boot Initiated #0xf1 | \
Initiated by power up | Asserted',
         '3 | 06/27/2013 | 21:01:13 | System Event #0xf4 |',
         ...
        ]
        >>> #
        >>> # Output trimmed for brevity
        >>> #

        :returns: The node's system event log
        :rtype: string
        """
        return self.bmc.sel_list()

    def get_sensors(self, search=""):
        """Get a list of sensor objects that match search criteria.

        .. note::
            * If no sensor name is specified, ALL sensors will be returned.

        >>> # Get ALL sensors ...
        >>> node.get_sensors()
        {
         'MP Temp 0'        : <pyipmi.sdr.AnalogSdr object at 0x1e63890>,
         'Temp 0'           : <pyipmi.sdr.AnalogSdr object at 0x1e63410>,
         'Temp 1'           : <pyipmi.sdr.AnalogSdr object at 0x1e638d0>,
         'Temp 2'           : <pyipmi.sdr.AnalogSdr object at 0x1e63690>,
         'Temp 3'           : <pyipmi.sdr.AnalogSdr object at 0x1e63950>,
         'VCORE Voltage'    : <pyipmi.sdr.AnalogSdr object at 0x1e63bd0>,
         'TOP Temp 2'       : <pyipmi.sdr.AnalogSdr object at 0x1e63ad0>,
         'TOP Temp 1'       : <pyipmi.sdr.AnalogSdr object at 0x1e63a50>,
         'TOP Temp 0'       : <pyipmi.sdr.AnalogSdr object at 0x1e639d0>,
         'VCORE Current'    : <pyipmi.sdr.AnalogSdr object at 0x1e63710>,
         'V18 Voltage'      : <pyipmi.sdr.AnalogSdr object at 0x1e63b50>,
         'V09 Current'      : <pyipmi.sdr.AnalogSdr object at 0x1e63990>,
         'Node Power'       : <pyipmi.sdr.AnalogSdr object at 0x1e63cd0>,
         'DRAM VDD Current' : <pyipmi.sdr.AnalogSdr object at 0x1e63910>,
         'DRAM VDD Voltage' : <pyipmi.sdr.AnalogSdr object at 0x1e634d0>,
         'V18 Current'      : <pyipmi.sdr.AnalogSdr object at 0x1e63c50>,
         'VCORE Power'      : <pyipmi.sdr.AnalogSdr object at 0x1e63c90>,
         'V09 Voltage'      : <pyipmi.sdr.AnalogSdr object at 0x1e63b90>
        }
        >>> # Get ANY sensor that 'contains' the substring of search in it ...
        >>> node.get_sensors(search='Temp 0')
        {
         'MP Temp 0'  : <pyipmi.sdr.AnalogSdr object at 0x1e63810>,
         'TOP Temp 0' : <pyipmi.sdr.AnalogSdr object at 0x1e63850>,
         'Temp 0'     : <pyipmi.sdr.AnalogSdr object at 0x1e63510>
        }

        :param search: Name of the sensor you wish to search for.
        :type search: string

        :return: Sensor information.
        :rtype: dictionary of pyipmi objects

        """
        sensors = [x for x in self.bmc.sdr_list()
                   if search.lower() in x.sensor_name.lower()]

        if (len(sensors) == 0):
            if (search == ""):
                raise NoSensorError("No sensors were found")
            else:
                raise NoSensorError("No sensors containing \"%s\" were " +
                                    "found" % search)
        return dict((x.sensor_name, x) for x in sensors)

    def get_sensors_dict(self, search=""):
        """Get a list of sensor dictionaries that match search criteria.

        >>> node.get_sensors_dict()
        {
         'DRAM VDD Current':
            {
             'entity_id'              : '7.1',
             'event_message_control'  : 'Per-threshold',
             'lower_critical'         : '34.200',
             'lower_non_critical'     : '34.200',
             'lower_non_recoverable'  : '34.200',
             'maximum_sensor_range'   : 'Unspecified',
             'minimum_sensor_range'   : 'Unspecified',
             'negative_hysteresis'    : '0.800',
             'nominal_reading'        : '50.200',
             'normal_maximum'         : '34.200',
             'normal_minimum'         : '34.200',
             'positive_hysteresis'    : '0.800',
             'sensor_name'            : 'DRAM VDD Current',
             'sensor_reading'         : '1.200 (+/- 0) Amps',
             'sensor_type'            : 'Current',
             'status'                 : 'ok',
             'upper_critical'         : '34.200',
             'upper_non_critical'     : '34.200',
             'upper_non_recoverable'  : '34.200'
            },
             ... #
             ... # Output trimmed for brevity ... many more sensors ...
             ... #
         'VCORE Voltage':
             {
              'entity_id'             : '7.1',
              'event_message_control' : 'Per-threshold',
              'lower_critical'        : '1.100',
              'lower_non_critical'    : '1.100',
              'lower_non_recoverable' : '1.100',
              'maximum_sensor_range'  : '0.245',
              'minimum_sensor_range'  : 'Unspecified',
              'negative_hysteresis'   : '0.020',
              'nominal_reading'       : '1.000',
              'normal_maximum'        : '1.410',
              'normal_minimum'        : '0.720',
              'positive_hysteresis'   : '0.020',
              'sensor_name'           : 'VCORE Voltage',
              'sensor_reading'        : '0 (+/- 0) Volts',
              'sensor_type'           : 'Voltage',
              'status'                : 'ok',
              'upper_critical'        : '0.675',
              'upper_non_critical'    : '0.695',
              'upper_non_recoverable' : '0.650'
             }
        }
        >>> # Get ANY sensor name that has the string 'Temp 0' in it ...
        >>> node.get_sensors_dict(search='Temp 0')
        {
         'MP Temp 0':
            {
             'entity_id'              : '7.1',
             'event_message_control'  : 'Per-threshold',
             'lower_critical'         : '2.000',
             'lower_non_critical'     : '5.000',
             'lower_non_recoverable'  : '0.000',
             'maximum_sensor_range'   : 'Unspecified',
             'minimum_sensor_range'   : 'Unspecified',
             'negative_hysteresis'    : '4.000',
             'nominal_reading'        : '25.000',
             'positive_hysteresis'    : '4.000',
             'sensor_name'            : 'MP Temp 0',
             'sensor_reading'         : '0 (+/- 0) degrees C',
             'sensor_type'            : 'Temperature',
             'status'                 : 'ok',
             'upper_critical'         : '70.000',
             'upper_non_critical'     : '55.000',
             'upper_non_recoverable'  : '75.000'
            },
         'TOP Temp 0':
             {
              'entity_id'             : '7.1',
              'event_message_control' : 'Per-threshold',
              'lower_critical'        : '2.000',
              'lower_non_critical'    : '5.000',
              'lower_non_recoverable' : '0.000',
              'maximum_sensor_range'  : 'Unspecified',
              'minimum_sensor_range'  : 'Unspecified',
              'negative_hysteresis'   : '4.000',
              'nominal_reading'       : '25.000',
              'positive_hysteresis'   : '4.000',
              'sensor_name'           : 'TOP Temp 0',
              'sensor_reading'        : '33 (+/- 0) degrees C',
              'sensor_type'           : 'Temperature',
              'status'                : 'ok',
              'upper_critical'        : '70.000',
              'upper_non_critical'    : '55.000',
              'upper_non_recoverable' : '75.000'
             },
         'Temp 0':
             {
              'entity_id'             : '3.1',
              'event_message_control' : 'Per-threshold',
              'lower_critical'        : '2.000',
              'lower_non_critical'    : '5.000',
              'lower_non_recoverable' : '0.000',
              'maximum_sensor_range'  : 'Unspecified',
              'minimum_sensor_range'  : 'Unspecified',
              'negative_hysteresis'   : '4.000',
              'nominal_reading'       : '25.000',
              'positive_hysteresis'   : '4.000',
              'sensor_name'           : 'Temp 0',
              'sensor_reading'        : '0 (+/- 0) degrees C',
              'sensor_type'           : 'Temperature',
              'status'                : 'ok',
              'upper_critical'        : '70.000',
              'upper_non_critical'    : '55.000',
              'upper_non_recoverable' : '75.000'
             }
        }

        .. note::
            * This function is the same as get_sensors(), only a dictionary of
              **{sensor : {attributes :values}}** is returned instead of an
              resultant pyipmi object.

        :param search: Name of the sensor you wish to search for.
        :type search: string

        :return: Sensor information.
        :rtype: dictionary of dictionaries

        """
        return dict((key, vars(value))
                    for key, value in self.get_sensors(search=search).items())

    def get_firmware_info(self):
        """Gets firmware info for each partition on the Node.

        >>> node.get_firmware_info()
        [<pyipmi.fw.FWInfo object at 0x2019850>,
        <pyipmi.fw.FWInfo object at 0x2019b10>,
        <pyipmi.fw.FWInfo object at 0x2019610>, ...]

        :return: Returns a list of FWInfo objects for each
        :rtype: list

        :raises IpmiError: If errors in the command occur with BMC \
communication.

        """
        fwinfo = [x for x in self.bmc.get_firmware_info()
                  if hasattr(x, "partition")]

        # Clean up the fwinfo results
        for entry in fwinfo:
            if (entry.version == ""):
                entry.version = "Unknown"

        return fwinfo

    def get_firmware_info_dict(self):
        """Gets firmware info for each partition on the Node.

        .. note::
            * This function is the same as get_firmware_info(), only a
              dictionary of **{attributes : values}** is returned instead of an
              resultant FWInfo object.


        >>> node.get_firmware_info_dict()
        [
            {'daddr'     : '20029000',
             'in_use'    : 'Unknown',
             'partition' : '00',
             'priority'  : '0000000c',
             'version'   : 'v0.9.1',
             'flags'     : 'fffffffd',
             'offset'    : '00000000',
             'type'      : '02 (S2_ELF)',
             'size'      : '00005000'},
             .... # Output trimmed for brevity.
             .... # partitions
             .... # 1 - 16
            {'daddr'     : '20029000',
             'in_use'    : 'Unknown',
             'partition' : '17',
             'priority'  : '0000000b',
             'version'   : 'v0.9.1',
             'flags'     : 'fffffffd',
             'offset'    : '00005000',
             'type'      : '02 (S2_ELF)',
             'size'      : '00005000'}
        ]

        :return: Returns a list of FWInfo objects for each
        :rtype: list

        :raises IpmiError: If errors in the command occur with BMC \
communication.

        """
        return [vars(info) for info in self.get_firmware_info()]

    def is_updatable(self, package, partition_arg="INACTIVE", priority=None):
        """Checks to see if the node can be updated with this firmware package.

        >>> from cxmanage_api.firmware_package import FirmwarePackage
        >>> fwpkg = FirmwarePackage('ECX-1000_update-v1.7.1-dirty.tar.gz')
        >>> fwpkg.version
        'ECX-1000-v1.7.1-dirty'
        >>> node.is_updatable(fwpkg)
        True

        :return: Whether the node is updatable or not.
        :rtype: boolean

        """
        try:
            self._check_firmware(package, partition_arg, priority)
            return True
        except (SocmanVersionError, FirmwareConfigError,
            PriorityIncrementError, NoPartitionError, ImageSizeError,
            PartitionInUseError):
            return False

    # pylint: disable=R0914, R0912, R0915
    def update_firmware(self, package, partition_arg="INACTIVE",
                          priority=None):
        """ Update firmware on this target.

        >>> from cxmanage_api.firmware_package import FirmwarePackage
        >>> fwpkg = FirmwarePackage('ECX-1000_update-v1.7.1-dirty.tar.gz')
        >>> fwpkg.version
        'ECX-1000-v1.7.1-dirty'
        >>> node.update_firmware(package=fwpkg)

        :param  package: Firmware package to deploy.
        :type package: `FirmwarePackage <firmware_package.html>`_
        :param partition_arg: Partition to upgrade to.
        :type partition_arg: string

        :raises PriorityIncrementError: If the SIMG Header priority cannot be
                                        changed.

        """

        new_directory = "~/.cxmanage/logs/%s" % self.ip_address
        new_directory = os.path.expanduser(new_directory)
        if not os.path.exists(new_directory):
            os.makedirs(new_directory)

        timestamp = time.strftime("%Y%m%d%H%M%S")
        new_filename = "%s-fwupdate.log" % timestamp
        new_filepath = os.path.join(new_directory, new_filename)

        logger = loggers.FileLogger(new_filepath)

        logger.info(
            "Firmware Update Log for Node %d" % self.node_id
        )
        logger.info("ECME IP address: " + self.ip_address)

        version_info = self.get_versions()
        logger.info(
            "\nOld firmware version: " + \
            version_info.firmware_version)

        if package.version:
            logger.info("New firmware version: " + package.version)
        else:
            logger.warn("New firmware version name unavailable.")

        logger.info(
            "\n[ Pre-Update Firmware Info for Node %d ]" %
            self.node_id
        )

        fwinfo = self.get_firmware_info()
        num_ubootenv_partitions = len([x for x in fwinfo
                                       if "UBOOTENV" in x.type])

        for partition in fwinfo:
            logger.info("\nPartition : %s" % partition.partition)
            info_string = "Type      : %s" % partition.type + \
            "\nOffset    : %s" % partition.offset + \
            "\nSize      : %s" % partition.size + \
            "\nPriority  : %s" % partition.priority + \
            "\nDaddr     : %s" % partition.daddr + \
            "\nFlags     : %s" % partition.flags + \
            "\nVersion   : %s" % partition.version + \
            "\nIn Use    : %s" % partition.in_use
            logger.info(info_string)

        # Get the new priority
        if (priority == None):
            priority = self._get_next_priority(fwinfo, package)

        logger.info(
            "\nPriority: " + str(priority)
        )

        images_to_upload = len(package.images)
        logger.info(
            "package.images: Images to upload: %d" % images_to_upload
        )

        updated_partitions = []

        image_uploading = 1
        for image in package.images:
            logger.info(
                "\nUploading image %d of %d" %
                (image_uploading, images_to_upload)
            )

            if image.type == "UBOOTENV" and num_ubootenv_partitions >= 2:
                logger.info(
                   "Trying ubootenv for image %d..." % image_uploading
                )

                # Get partitions
                running_part = self._get_partition(fwinfo, image.type, "FIRST")
                factory_part = self._get_partition(fwinfo, image.type,
                        "SECOND")

                # Extra \n's here for ease of reading output
                logger.info(
                    "\nFirst ('FIRST') partition:\n" + \
                    str(running_part) + \
                    "\n\nSecond ('FACTORY') partition:\n" + \
                    str(factory_part)
                )

                # Update factory ubootenv
                self._upload_image(image, factory_part, priority)

                # Extra \n for output formatting
                logger.info(
                    "\nDone uploading factory image"
                )

                # Update running ubootenv
                old_ubootenv_image = self._download_image(running_part)
                old_ubootenv = self.ubootenv(open(
                                        old_ubootenv_image.filename, "rb").read())

                logger.info(
                   "Done getting old ubootenv image"
                )

                try:
                    ubootenv = self.ubootenv(open(image.filename, "rb").read())
                    ubootenv.set_boot_order(old_ubootenv.get_boot_order())
                    ubootenv.set_pxe_interface(old_ubootenv.get_pxe_interface())

                    logger.info(
                        "Set boot order to %s" % old_ubootenv.get_boot_order()
                    )

                    filename = temp_file()
                    with open(filename, "wb") as file_:
                        file_.write(ubootenv.get_contents())

                    ubootenv_image = self.image(filename, image.type, False,
                                           image.daddr, image.skip_crc32,
                                           image.version)
                    self._upload_image(ubootenv_image, running_part,
                            priority)

                    logger.info(
                        "Done uploading ubootenv image to first " + \
                        "partition ('running partition')"
                    )
                except (ValueError, UbootenvError):
                    self._upload_image(image, running_part, priority)

                updated_partitions += [running_part, factory_part]
            else:
                logger.info(
                   "Using Non-ubootenv for image %d..." %
                   image_uploading
                )
                # Get the partitions
                if (partition_arg == "BOTH"):
                    partitions = [self._get_partition(fwinfo, image.type,
                            "FIRST"), self._get_partition(fwinfo, image.type,
                            "SECOND")]
                else:
                    partitions = [self._get_partition(fwinfo, image.type,
                            partition_arg)]

                # Update the image
                for partition in partitions:
                    self._upload_image(image, partition, priority)

                updated_partitions += partitions

            logger.info(
                "Done uploading image %d of %d" %
                (image_uploading, images_to_upload)
            )
            image_uploading = image_uploading + 1

        if package.version:
            self.bmc.set_firmware_version(package.version)

            logger.info("")  # For readability

        # Post verify
        fwinfo = self.get_firmware_info()
        for old_partition in updated_partitions:
            partition_id = int(old_partition.partition)
            new_partition = fwinfo[partition_id]

            if new_partition.type != old_partition.type:
                logger.error(
                    "Update failed (partition %i, type changed)"
                    % partition_id
                )
                raise Exception("Update failed (partition %i, type changed)"
                        % partition_id)

            if int(new_partition.priority, 16) != priority:
                logger.error(
                    "Update failed (partition %i, wrong priority)"
                    % partition_id
                )
                raise Exception("Update failed (partition %i, wrong priority)"
                        % partition_id)

            if int(new_partition.flags, 16) & 2 != 0:
                logger.error(
                    "Update failed (partition %i, not activated)"
                    % partition_id
                )
                raise Exception("Update failed (partition %i, not activated)"
                        % partition_id)

            self.bmc.check_firmware(partition_id)
            logger.info(
                "Check complete for partition %d" % partition_id
            )

        logger.info(
            "\nDone updating firmware."
        )

        print("\nLog saved to " + new_filepath)

    def update_node_eeprom(self, image):
        """Updates the node EEPROM

        .. note::
            A power cycle is required for the update to take effect

        >>> node.update_node_eeprom('builds/dual_node_0_v3.0.0.img')

        :param image: The location of an EEPROM image
        :type image: string

        :raises EEPROMUpdateError: When an error is encountered while \
updating the EEPROM

        """
        # Does the image exist?
        if(not os.path.exists(image)):
            raise EEPROMUpdateError(
                '%s does not exist' % image
            )
        node_hw_ver = self.get_versions().hardware_version
        # Is this configuration valid for EEPROM updates?
        if('Dual Node' not in node_hw_ver):
            raise EEPROMUpdateError(
                'eepromupdate is only valid on TerraNova systems'
            )
        # Is this image valid?
        if('Uplink' in node_hw_ver):
            image_prefix = 'dual_uplink_node_%s' % (self.node_id % 4)
        else:
            image_prefix = 'dual_node_%s' % (self.node_id % 4)
        if(image_prefix not in image):
            raise EEPROMUpdateError(
                '%s is not a valid node EEPROM image for this node' % image
            )
        # Perform the upgrade
        ipmi_command = 'fru write 81 %s' % image
        self.ipmitool_command(ipmi_command.split(' '))

    def update_slot_eeprom(self, image):
        """Updates the slot EEPROM

        .. note::
            A power cycle is required for the update to take effect

        >>> node.update_slot_eeprom('builds/tn_storage.single_slot_v3.0.0.img')

        :param image: The location of an EEPROM image
        :type image: string

        :raises EEPROMUpdateError: When an error is encountered while \
updating the EEPROM

        """
        # Does the image exist?
        if(not os.path.exists(image)):
            raise EEPROMUpdateError(
                '%s does not exist' % image
            )
        node_hw_ver = self.get_versions().hardware_version
        # Is this configuration valid for EEPROM updates?
        if('Dual Node' not in node_hw_ver):
            raise EEPROMUpdateError(
                'eepromupdate is only valid on TerraNova systems'
            )
        # Is this image valid?
        if('tn_storage.single_slot' not in image):
            raise EEPROMUpdateError(
                '%s is an invalid image for slot EEPROM' % image
            )
        # Perform the upgrade
        ipmi_command = 'fru write 82 %s' % image
        self.ipmitool_command(ipmi_command.split(' '))

    def config_reset(self):
        """Resets configuration to factory defaults.

        >>> node.config_reset()

        :raises IpmiError: If errors in the command occur with BMC \
communication.

        """
        # Reset CDB
        self.bmc.reset_firmware()

        # Reset ubootenv
        fwinfo = self.get_firmware_info()
        try:
            running_part = self._get_partition(fwinfo, "UBOOTENV", "FIRST")
            factory_part = self._get_partition(fwinfo, "UBOOTENV", "SECOND")
            image = self._download_image(factory_part)
            self._upload_image(image, running_part)
        except NoPartitionError:
            pass  # Only one partition? Don't mess with it!

        # Clear SEL
        self.bmc.sel_clear()

    def set_boot_order(self, boot_args):
        """Sets boot-able device order for this node.

        >>> node.set_boot_order(boot_args=['pxe', 'disk'])

        :param boot_args: Arguments list to pass on to the uboot environment.
        :type boot_args: list

        """
        fwinfo = self.get_firmware_info()
        first_part = self._get_partition(fwinfo, "UBOOTENV", "FIRST")
        active_part = self._get_partition(fwinfo, "UBOOTENV", "ACTIVE")

        # Download active ubootenv, modify, then upload to first partition
        image = self._download_image(active_part)
        ubootenv = self.ubootenv(open(image.filename).read())
        ubootenv.set_boot_order(boot_args)
        priority = max(int(x.priority, 16) for x in [first_part, active_part])

        filename = temp_file()
        with open(filename, "wb") as file_:
            file_.write(ubootenv.get_contents())

        ubootenv_image = self.image(filename, image.type, False, image.daddr,
                                    image.skip_crc32, image.version)
        self._upload_image(ubootenv_image, first_part, priority)

    def get_boot_order(self):
        """Returns the boot order for this node.

        >>> node.get_boot_order()
        ['pxe', 'disk']

        """
        return self.get_ubootenv().get_boot_order()

    def set_pxe_interface(self, interface):
        """Sets pxe interface for this node.

        >>> node.set_boot_order('eth0')

        :param interface: Interface pass on to the uboot environment.
        :type boot_args: string

        """
        fwinfo = self.get_firmware_info()
        first_part = self._get_partition(fwinfo, "UBOOTENV", "FIRST")
        active_part = self._get_partition(fwinfo, "UBOOTENV", "ACTIVE")

        # Download active ubootenv, modify, then upload to first partition
        image = self._download_image(active_part)
        ubootenv = self.ubootenv(open(image.filename).read())
        ubootenv.set_pxe_interface(interface)
        priority = max(int(x.priority, 16) for x in [first_part, active_part])

        filename = temp_file()
        with open(filename, "w") as file_:
            file_.write(ubootenv.get_contents())

        ubootenv_image = self.image(filename, image.type, False, image.daddr,
                                    image.skip_crc32, image.version)
        self._upload_image(ubootenv_image, first_part, priority)

    def get_pxe_interface(self):
        """Returns the current pxe interface for this node.

        >>> node.get_pxe_interface()
        'eth0'
        """
        return self.get_ubootenv().get_pxe_interface()

    def get_versions(self):
        """Get version info from this node.

        >>> node.get_versions()
        <pyipmi.info.InfoBasicResult object at 0x2019b90>
        >>> # Some useful information ...
        >>> info.a9boot_version
        'v2012.10.16'
        >>> info.cdb_version
        'v0.9.1'

        :returns: The results of IPMI info basic command.
        :rtype: pyipmi.info.InfoBasicResult

        :raises IpmiError: If errors in the command occur with BMC \
communication.
        :raises Exception: If there are errors within the command response.

        """
        result = self.bmc.get_info_basic()
        fwinfo = self.get_firmware_info()
        fw_version = result.firmware_version

        # components maps variables to firmware partition types
        components = [
            ("cdb_version", "CDB"),
            ("stage2_version", "S2_ELF"),
            ("bootlog_version", "BOOT_LOG")
        ]
        # Use firmware version to determine the chip type and name
        # In the future, we may want to determine the chip name some other way
        if fw_version.startswith("ECX-1000"):
            components.append(("a9boot_version", "A9_EXEC"))
            setattr(result, "chip_name", "Highbank")
        elif fw_version.startswith("ECX-2000"):
            # The BMC (and fwinfo) still reference the A15 as an A9
            components.append(("a15boot_version", "A9_EXEC"))
            setattr(result, "chip_name", "Midway")
        else:
            # Default to A9 and unknown name
            components.append(("a9boot_version", "A9_EXEC"))
            setattr(result, "chip_name", "Unknown")
        components.append(("uboot_version", "A9_UBOOT"))
        components.append(("ubootenv_version", "UBOOTENV"))
        components.append(("dtb_version", "DTB"))

        for var, ptype in components:
            try:
                partition = self._get_partition(fwinfo, ptype, "ACTIVE")
                setattr(result, var, partition.version)
            except NoPartitionError:
                pass
        try:
            card = self.bmc.get_info_card()
            setattr(result, "hardware_version", "%s X%02i" %
                    (card.type, int(card.revision)))
        except IpmiError as err:
            if (self.verbose):
                print str(err)
            # Should raise an error, but we want to allow the command
            # to continue gracefully if the ECME is out of date.
            setattr(result, "hardware_version", "Unknown")
        return result

    def get_versions_dict(self):
        """Get version info from this node.

        .. note::
            * This function is the same as get_versions(), only a dictionary of
              **{attributes : values}** is returned instead of an resultant
              pyipmi object.

        >>> n.get_versions_dict()
        {'soc_version'      : 'v0.9.1',
         'build_number'     : '7E10987C',
         'uboot_version'    : 'v2012.07_cx_2012.10.29',
         'ubootenv_version' : 'v2012.07_cx_2012.10.29',
         'timestamp'        : '1352911670',
         'cdb_version'      : 'v0.9.1-39-g7e10987',
         'header'           : 'Calxeda SoC (0x0096CD)',
         'version'          : 'ECX-1000-v1.7.1',
         'bootlog_version'  : 'v0.9.1-39-g7e10987',
         'a9boot_version'   : 'v2012.10.16',
         'stage2_version'   : 'v0.9.1',
         'dtb_version'      : 'v3.6-rc1_cx_2012.10.02',
         'card'             : 'EnergyCard X02'
        }

        :returns: The results of IPMI info basic command.
        :rtype: dictionary

        :raises IpmiError: If errors in the command occur with BMC \
communication.
        :raises Exception: If there are errors within the command response.

        """
        return vars(self.get_versions())

    def ipmitool_command(self, ipmitool_args):
        """Send a raw ipmitool command to the node.

        >>> node.ipmitool_command(['cxoem', 'info', 'basic'])
        'Calxeda SoC (0x0096CD)\\n  Firmware Version: ECX-1000-v1.7.1-dirty\\n
        SoC Version: 0.9.1\\n  Build Number: A69523DC \\n
        Timestamp (1351543656): Mon Oct 29 15:47:36 2012'

        :param ipmitool_args: Arguments to pass to the ipmitool.
        :type ipmitool_args: list

        """
        if ("IPMITOOL_PATH" in os.environ):
            command = [os.environ["IPMITOOL_PATH"]]
        else:
            command = ["ipmitool"]

        command += ["-U", self.username, "-P", self.password, "-H",
                self.ip_address]
        command += ipmitool_args

        if (self.verbose):
            print "Running %s" % " ".join(command)

        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return (stdout + stderr).strip()

    def get_ubootenv(self):
        """Get the active u-boot environment.

        >>> node.get_ubootenv()
        <cxmanage_api.ubootenv.UbootEnv instance at 0x209da28>

        :return: U-Boot Environment object.
        :rtype: `UBootEnv <ubootenv.html>`_

        """
        fwinfo = self.get_firmware_info()
        partition = self._get_partition(fwinfo, "UBOOTENV", "ACTIVE")
        image = self._download_image(partition)
        return self.ubootenv(open(image.filename, "rb").read())

    def get_fabric_ipinfo(self):
        """Gets what ip information THIS node knows about the Fabric.

        >>> node.get_fabric_ipinfo()
        {0: '10.20.1.9', 1: '10.20.2.131', 2: '10.20.0.220', 3: '10.20.2.5'}

        :return: Returns a map of node_ids->ip_addresses.
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.
        :raises TftpException: If the TFTP transfer fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_config_get_ip_info'
        )

        # Parse addresses from ipinfo file
        results = {}
        for line in open(filename):
            if (line.startswith("Node")):
                elements = line.split()
                node_id = int(elements[1].rstrip(":"))
                node_ip_address = elements[2]

                # Old boards used to return 0.0.0.0 sometimes -- might not be
                # an issue anymore.
                if (node_ip_address != "0.0.0.0"):
                    results[node_id] = node_ip_address

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_fabric_macaddrs(self):
        """Gets what macaddr information THIS node knows about the Fabric.

        >>> node.get_fabric_macaddrs()
        {0: {0: ['fc:2f:40:ab:cd:cc'],
          1: ['fc:2f:40:ab:cd:cd'],
          2: ['fc:2f:40:ab:cd:ce']},
         1: {0: ['fc:2f:40:3e:66:e0'],
          1: ['fc:2f:40:3e:66:e1'],
          2: ['fc:2f:40:3e:66:e2']},
         2: {0: ['fc:2f:40:fd:37:34'],
          1: ['fc:2f:40:fd:37:35'],
          2: ['fc:2f:40:fd:37:36']},
         3: {0: ['fc:2f:40:0e:4a:74'],
          1: ['fc:2f:40:0e:4a:75'],
          2: ['fc:2f:40:0e:4a:76']}}

        :return: Returns a map of node_ids->ports->mac_addresses.
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.
        :raises TftpException: If the TFTP transfer fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_config_get_mac_addresses'
        )

        # Parse addresses from ipinfo file
        results = {}
        for line in open(filename):
            if (line.startswith("Node")):
                elements = line.split()
                node_id = int(elements[1].rstrip(","))
                port = int(elements[3].rstrip(":"))
                mac_address = elements[4]

                if not node_id in results:
                    results[node_id] = {}
                if not port in results[node_id]:
                    results[node_id][port] = []
                results[node_id][port].append(mac_address)

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_fabric_uplink_info(self):
        """Gets what uplink information THIS node knows about the Fabric.

        >>> node.get_fabric_uplink_info()
        {'0': {'eth0': '0', 'eth1': '0', 'mgmt': '0'},
         '1': {'eth0': '0', 'eth1': '0', 'mgmt': '0'},
         '2': {'eth0': '0', 'eth1': '0', 'mgmt': '0'},
         '3': {'eth0': '0', 'eth1': '0', 'mgmt': '0'},
         '4': {'eth0': '0', 'eth1': '0', 'mgmt': '0'}}

        :return: Returns a map of {node_id : {interface : uplink}}
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.
        :raises TftpException: If the TFTP transfer fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_config_get_uplink_info'
        )

        # Parse addresses from ipinfo file
        results = {}
        for line in open(filename):
            node_id = int(line.replace('Node ', '')[0])
            ul_info = line.replace('Node %s:' % node_id, '').strip().split(',')
            node_data = {}
            for ul_ in ul_info:
                data = tuple(ul_.split())
                node_data[data[0]] = int(data[1])
            results[node_id] = node_data

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_link_stats(self, link=0):
        """Gets the linkstats for the link specified.

        >>> node.get_link_stats()
        {'FS_LC0_BYTE_CNT_0': '0x0',
         'FS_LC0_BYTE_CNT_1': '0x0',
         'FS_LC0_CFG_0': '0x1000d07f',
         'FS_LC0_CFG_1': '0x105f',
         'FS_LC0_CM_RXDATA_0': '0x0',
         'FS_LC0_CM_RXDATA_1': '0x0',
         'FS_LC0_CM_TXDATA_0': '0x82000002',
         'FS_LC0_CM_TXDATA_1': '0x0',
         'FS_LC0_PKT_CNT_0': '0x0',
         'FS_LC0_PKT_CNT_1': '0x0',
         'FS_LC0_RDRPSCNT': '0x3e791',
         'FS_LC0_RERRSCNT': '0x0',
         'FS_LC0_RMCSCNT': '0x173b923',
         'FS_LC0_RPKTSCNT': '0x0',
         'FS_LC0_RUCSCNT': '0x43cab',
         'FS_LC0_SC_STAT': '0x0',
         'FS_LC0_STATE': '0x1033',
         'FS_LC0_TDRPSCNT': '0x0',
         'FS_LC0_TPKTSCNT': '0x1'}

        :param link: The link to get stats for (0-4).
        :type link: integer

        :returns: The linkstats for the link specified.
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_get_linkstats',
            link=link
        )
        results = {}
        for line in open(filename):
            if ('=' in line):
                reg_value = line.strip().split('=')
                if (len(reg_value) < 2):
                    raise ValueError(
                        'Register: %s has no value!' % reg_value[0]
                    )
                else:
                    results[
                        reg_value[0].replace(
                            'pFS_LCn', 'FS_LC%s' % link
                        ).replace('(link)', '').strip()
                    ] = reg_value[1].strip()

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_linkmap(self):
        """Gets the src and destination of each link on a node.

        >>> node.get_linkmap()
        {1: 2, 3: 1, 4: 3}

        :return: Returns a map of link_id->node_id.
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.
        :raises TftpException: If the TFTP transfer fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_info_get_link_map',
        )

        results = {}
        for line in open(filename):
            if (line.startswith("Link")):
                elements = line.strip().split()
                link_id = int(elements[1].rstrip(':'))
                node_id = int(elements[3].strip())
                results[link_id] = node_id

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_routing_table(self):
        """Gets the routing table as instantiated in the fabric switch.

        >>> node.get_routing_table()
        {1: [0, 0, 0, 3, 0], 2: [0, 3, 0, 0, 2], 3: [0, 2, 0, 0, 3]}

        :return: Returns a map of node_id->rt_entries.
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.
        :raises TftpException: If the TFTP transfer fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_info_get_routing_table',
        )

        results = {}
        for line in open(filename):
            if (line.startswith("Node")):
                elements = line.strip().split()
                node_id = int(elements[1].rstrip(':'))
                rt_entries = []
                for entry in elements[4].strip().split('.'):
                    rt_entries.append(int(entry))
                results[node_id] = rt_entries

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_depth_chart(self):
        """Gets a table indicating the distance from a given node to all other
        nodes on each fabric link.

        >>> node.get_depth_chart()
        {1: {'shortest': (0, 0)},
         2: {'others': [(3, 1)], 'shortest': (0, 0)},
         3: {'others': [(2, 1)], 'shortest': (0, 0)}}

        :return: Returns a map of target->(neighbor, hops),
                                  [other (neighbors,hops)]
        :rtype: dictionary

        :raises IpmiError: If the IPMI command fails.
        :raises TftpException: If the TFTP transfer fails.

        """
        filename = self._run_fabric_command(
            function_name='fabric_info_get_depth_chart',
        )

        results = {}
        for line in open(filename):
            if (line.startswith("Node")):
                elements = line.strip().split()
                target = int(elements[1].rstrip(':'))
                neighbor = int(elements[8].rstrip(':'))
                hops = int(elements[4].strip())
                dchrt_entries = {}
                dchrt_entries['shortest'] = (neighbor, hops)
                try:
                    other_hops_neighbors = elements[12].strip().split(
                        r'[,\s]+'
                    )
                    hops = []
                    for entry in other_hops_neighbors:
                        pair = entry.strip().split('/')
                        hops.append((int(pair[1]), int(pair[0])))
                    dchrt_entries['others'] = hops

                except Exception:  # pylint: disable=W0703
                    pass

                results[target] = dchrt_entries

        # Make sure we found something
        if (not results):
            raise TftpException("Node failed to reach TFTP server")

        return results

    def get_server_ip(self, interface=None, ipv6=False, user="user1",
            password="1Password", aggressive=False):
        """Get the IP address of the Linux server. The server must be powered
        on for this to work.

        >>> node.get_server_ip()
        '192.168.100.100'

        :param interface: Network interface to check (e.g. eth0).
        :type interface: string
        :param ipv6: Return an IPv6 address instead of IPv4.
        :type ipv6: boolean
        :param user: Linux username.
        :type user: string
        :param password: Linux password.
        :type password: string
        :param aggressive: Discover the IP aggressively (may power cycle node).
        :type aggressive: boolean

        :return: The IP address of the server.
        :rtype: string
        :raises IpmiError: If errors in the command occur with BMC \
communication.
        :raises IPDiscoveryError: If the server is off, or the IP can't be \
obtained.

        """
        verbosity = 2 if self.verbose else 0
        retriever = self.ipretriever(self.ip_address, aggressive=aggressive,
                verbosity=verbosity, server_user=user, server_password=password,
                interface=interface, ipv6=ipv6, bmc=self.bmc)
        retriever.run()
        return retriever.server_ip

    def get_linkspeed(self, link=None, actual=False):
        """Get the linkspeed for the node.  This returns either
        the actual linkspeed based on phy controller register settings,
        or if sent to a primary node, the linkspeed setting for the
        Profile 0 of the currently active Configuration.

        >>> node.get_linkspeed()
        2.5

        :param link: The fabric link number to read the linkspeed for.
        :type link: integer
        :param actual: WhetherThe fabric link number to read the linkspeed for.
        :type actual: boolean

        :return: Linkspeed for the fabric.
        :rtype: float

        """
        return self.bmc.fabric_get_linkspeed(link=link, actual=actual)

    def get_uplink(self, iface=0):
        """Get the uplink a MAC will use when transmitting a packet out of the
        cluster.

        >>> node.get_uplink(iface=1)
        0

        :param iface: The interface for the uplink.
        :type iface: integer

        :return: The uplink iface is connected to.
        :rtype: integer

        :raises IpmiError: When any errors are encountered.

        """
        return self.bmc.fabric_config_get_uplink(iface=iface)

    def set_uplink(self, uplink=0, iface=0):
        """Set the uplink a MAC will use when transmitting a packet out of the
        cluster.

        >>> #
        >>> # Set eth0 to uplink 1 ...
        >>> #
        >>> node.set_uplink(uplink=1,iface=0)

        :param uplink: The uplink to set.
        :type uplink: integer
        :param iface: The interface for the uplink.
        :type iface: integer

        :raises IpmiError: When any errors are encountered.

        """
        return self.bmc.fabric_config_set_uplink(
            uplink=uplink,
            iface=iface
        )

    def get_uplink_speed(self):
        """Get the uplink speed of this node.

        >>> node.get_uplink_speed()
        1

        :return: The uplink speed of this node, in Gbps
        :rtype: integer

        """
        return self.bmc.fabric_get_uplink_speed()

    def get_uplink_info(self):
        """Get the uplink information for this node.

        >>> node.get_uplink_info()
        'Node 0: eth0 0, eth1 0, mgmt 0'

        :return: The uplink information for this node
        :rtype: string

        """
        return self.bmc.fabric_get_uplink_info().strip()

    def get_node_fru_version(self):
        """Get the node FRU version.

        >>> node.get_node_fru_version
        'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c'

        :return: The node FRU version of this node
        :rtype: string

        This is essentially the equivalent of ipmitool FRU read 81 filename
        and reading only the version from that file.
        The in-file offset for the node FRU version is 516, and the
        length of the version string is 40 bytes.

        """
        version = self._read_fru(81, offset=516, bytes_to_read=40)
        # If there is an error reading the FRU, every byte could be x00
        if version == "\x00"*len(version):
            raise NoFRUVersionError("No node FRU detected")

        # If the version string is less than 40 bytes long, remove the x00's
        version = version.replace("\x00", "")

        return version

    def get_slot_fru_version(self):
        """Get the slot FRU version.

        >>> node.get_slot_fru_version
        'Unknown'

        :return: The slot FRU version of this node
        :rtype: string

        This is essentially the equivalent of ipmitool FRU read 82 filename
        and reading only the version from that file.
        The in-file offset for the node FRU version is 516, and the
        length of the version string is 40 bytes.

        Note that some system boards do not have slot FRUs, and are
        therefore expected to raise an exception.

        """
        version = self._read_fru(82, offset=516, bytes_to_read=40)
        # If there is an error reading the FRU, every byte could be x00
        if version == "\x00"*len(version):
            raise NoFRUVersionError("No slot FRU detected.")

        # If the version string is less than 40 bytes long, remove the x00's
        version = version.replace("\x00", "")

        return version

    def _run_fabric_command(self, function_name, **kwargs):
        """Handles the basics of sending a node a command for fabric data."""
        filename = temp_file()
        basename = os.path.basename(filename)
        try:
            getattr(self.bmc, function_name)(filename=basename, **kwargs)
            self.ecme_tftp.get_file(basename, filename)

        except (IpmiError, TftpException):
            getattr(self.bmc, function_name)(
                filename=basename,
                tftp_addr=self.tftp_address,
                **kwargs
            )

            deadline = time.time() + 10
            while (time.time() < deadline):
                try:
                    time.sleep(1)
                    self.tftp.get_file(src=basename, dest=filename)
                    if (os.path.getsize(filename) > 0):
                        break

                except (TftpException, IOError):
                    pass

        return filename

    @staticmethod
    def _get_partition(fwinfo, image_type, partition_arg):
        """Get a partition for this image type based on the argument."""
        # Filter partitions for this type
        partitions = [x for x in fwinfo if
                      x.type.split()[1][1:-1] == image_type]
        if (len(partitions) < 1):
            raise NoPartitionError("No partition of type %s found on host"
                    % image_type)

        if (partition_arg == "FIRST"):
            return partitions[0]
        elif (partition_arg == "SECOND"):
            if (len(partitions) < 2):
                raise NoPartitionError("No second partition found on host")
            return partitions[1]
        elif (partition_arg == "OLDEST"):
            # Return the oldest partition
            partitions.sort(key=lambda x: x.partition, reverse=True)
            partitions.sort(key=lambda x: x.priority)
            return partitions[0]
        elif (partition_arg == "NEWEST"):
            # Return the newest partition
            partitions.sort(key=lambda x: x.partition)
            partitions.sort(key=lambda x: x.priority, reverse=True)
            return partitions[0]
        elif (partition_arg == "INACTIVE"):
            # Return the partition that's not in use (or least likely to be)
            partitions.sort(key=lambda x: x.partition, reverse=True)
            partitions.sort(key=lambda x: x.priority)
            partitions.sort(key=lambda x: int(x.flags, 16) & 2 == 0)
            partitions.sort(key=lambda x: x.in_use == "1")
            return partitions[0]
        elif (partition_arg == "ACTIVE"):
            # Return the partition that's in use (or most likely to be)
            partitions.sort(key=lambda x: x.partition)
            partitions.sort(key=lambda x: x.priority, reverse=True)
            partitions.sort(key=lambda x: int(x.flags, 16) & 2 == 1)
            partitions.sort(key=lambda x: x.in_use == "0")
            return partitions[0]
        else:
            raise ValueError("Invalid partition argument: %s" % partition_arg)

    def _upload_image(self, image, partition, priority=None):
        """Upload a single image. This includes uploading the image, performing
        the firmware update, crc32 check, and activation.
        """
        partition_id = int(partition.partition)
        if (priority == None):
            priority = int(partition.priority, 16)
        daddr = int(partition.daddr, 16)

        # Check image size
        if (image.size() > int(partition.size, 16)):
            raise ImageSizeError("%s image is too large for partition %i" %
                    (image.type, partition_id))

        filename = image.render_to_simg(priority, daddr)
        basename = os.path.basename(filename)

        for _ in xrange(2):
            try:
                self.bmc.register_firmware_write(
                    basename,
                    partition_id,
                    image.type
                )
                self.ecme_tftp.put_file(filename, basename)
                break
            except (IpmiError, TftpException):
                pass
        else:
            # Fall back and use TFTP server
            self.tftp.put_file(filename, basename)
            result = self.bmc.update_firmware(basename, partition_id,
                    image.type, self.tftp_address)
            self._wait_for_transfer(result.tftp_handle_id)

        # Verify crc and activate
        self.bmc.check_firmware(partition_id)
        self.bmc.activate_firmware(partition_id)

    def _download_image(self, partition):
        """Download an image from the target."""
        filename = temp_file()
        basename = os.path.basename(filename)
        partition_id = int(partition.partition)
        image_type = partition.type.split()[1][1:-1]

        for _ in xrange(2):
            try:
                self.bmc.register_firmware_read(
                    basename,
                    partition_id,
                    image_type
                )
                self.ecme_tftp.get_file(basename, filename)
                break
            except (IpmiError, TftpException):
                pass
        else:
            # Fall back and use TFTP server
            result = self.bmc.retrieve_firmware(basename, partition_id,
                    image_type, self.tftp_address)
            self._wait_for_transfer(result.tftp_handle_id)
            self.tftp.get_file(basename, filename)

        return self.image(filename=filename, image_type=image_type,
                          daddr=int(partition.daddr, 16),
                          version=partition.version)

    def _wait_for_transfer(self, handle):
        """Wait for a firmware transfer to finish."""
        deadline = time.time() + 180
        result = self.bmc.get_firmware_status(handle)

        while (result.status == "In progress"):
            if (time.time() >= deadline):
                raise TimeoutError("Transfer timed out after 3 minutes")
            time.sleep(1)
            result = self.bmc.get_firmware_status(handle)

        if (result.status != "Complete"):
            raise TransferFailure("Node reported TFTP transfer failure")

    def _check_firmware(self, package, partition_arg="INACTIVE", priority=None):
        """Check if this host is ready for an update."""
        info = self.get_versions()
        fwinfo = self.get_firmware_info()
        num_ubootenv_partitions = len([x for x in fwinfo
                                       if "UBOOTENV" in x.type])

        # Check firmware version
        if package.version and info.firmware_version:
            package_match = re.match("^ECX-[0-9]+", package.version)
            firmware_match = re.match("^ECX-[0-9]+", info.firmware_version)
            if package_match and firmware_match:
                package_version = package_match.group(0)
                firmware_version = firmware_match.group(0)
                if package_version != firmware_version:
                    raise FirmwareConfigError(
                            "Refusing to upload an %s package to an %s host"
                            % (package_version, firmware_version))

        # Check socman version
        if (package.required_socman_version):
            ecme_version = info.ecme_version.lstrip("v")
            required_version = package.required_socman_version.lstrip("v")
            if ((package.required_socman_version and
                 parse_version(ecme_version)) <
                 parse_version(required_version)):
                raise SocmanVersionError(
                        "Update requires socman version %s (found %s)"
                        % (required_version, ecme_version))

        # Check slot0 vs. slot2
        if (package.config and info.firmware_version != "Unknown" and
            len(info.firmware_version) < 32):
            firmware_config = "default"

            if (package.config != firmware_config):
                raise FirmwareConfigError(
                        "Refusing to upload a \'%s\' package to a \'%s\' host"
                        % (package.config, firmware_config))

        # Check that the priority can be bumped
        if (priority == None):
            priority = self._get_next_priority(fwinfo, package)

        # Check partitions
        for image in package.images:
            if (image.type == "UBOOTENV" and num_ubootenv_partitions >= 2
                    or partition_arg == "BOTH"):
                partitions = [self._get_partition(fwinfo, image.type, x)
                        for x in ["FIRST", "SECOND"]]
            else:
                partitions = [self._get_partition(fwinfo, image.type,
                        partition_arg)]

            for partition in partitions:
                if (image.size() > int(partition.size, 16)):
                    raise ImageSizeError(
                            "%s image is too large for partition %i"
                            % (image.type, int(partition.partition)))

                if (image.type in ["CDB", "BOOT_LOG"] and
                        partition.in_use == "1"):
                    raise PartitionInUseError(
                        "Can't upload to a CDB/BOOT_LOG partition " +
                        "that's in use"
                    )

        # Try a TFTP download. Would try an upload too, but nowhere to put it.
        partition = self._get_partition(fwinfo, "SOC_ELF", "FIRST")
        self._download_image(partition)

    @staticmethod
    def _get_next_priority(fwinfo, package):
        """ Get the next priority """
        priority = None
        image_types = [x.type for x in package.images]
        for partition in fwinfo:
            partition_active = int(partition.flags, 16) & 2
            partition_type = partition.type.split()[1].strip("()")
            if ((not partition_active) and (partition_type in image_types)):
                priority = max(priority, int(partition.priority, 16) + 1)
        if (priority > 0xFFFF):
            raise PriorityIncrementError(
                            "Unable to increment SIMG priority, too high")
        return priority

    def _read_fru(self, fru_number, offset=0, bytes_to_read=-1):
        """Read from node's fru starting at offset.
        This is equivalent to the ipmitool fru read command.

        """
        # Use a temporary file to store the FRU image
        with tempfile.NamedTemporaryFile(delete=True) as hexfile:
            self.bmc.fru_read(fru_number, hexfile.name)
            hexfile.seek(offset)
            return(hexfile.read(bytes_to_read))


# End of file: ./node.py
