# pylint: disable=C0302
"""Calxeda: fabric.py """


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

from cxmanage_api.tasks import DEFAULT_TASK_QUEUE
from cxmanage_api.tftp import InternalTftp
from cxmanage_api.node import Node as NODE
from cxmanage_api.cx_exceptions import CommandFailedError


# pylint: disable=R0902,R0903, R0904
class Fabric(object):
    """ The Fabric class provides management of multiple nodes.

    >>> from cxmanage_api.fabric import Fabric
    >>> fabric = Fabric('10.20.1.9')

    :param ip_address: The ip_address of ANY known node for the Fabric.
    :type ip_address: string
    :param username: The login username credential. [Default admin]
    :type username: string
    :param password: The login password credential. [Default admin]
    :type password: string
    :param tftp: Tftp server to facilitate IPMI command responses.
    :type tftp: `Tftp <tftp.html>`_
    :param task_queue: TaskQueue to use for sending commands.
    :type task_queue: `TaskQueue <tasks.html#cxmanage_api.tasks.TaskQueue>`_
    :param verbose: Flag to turn on verbose output (cmd/response).
    :type verbose: boolean
    :param node: Node type, for dependency integration.
    :type node: `Node <node.html>`_
    """

    class CompositeBMC(object):
        """ Composite BMC object. Provides a mechanism to run BMC
        commands in parallel across all nodes.
        """

        def __init__(self, fabric):
            self.fabric = fabric

        def __getattr__(self, name):
            """ If the underlying BMCs have a method by this name, then return
            a callable function that does it in parallel across all nodes.
            """
            nodes = self.fabric.nodes
            task_queue = self.fabric.task_queue

            for node in nodes.values():
                if ((not hasattr(node.bmc, name)) or
                    (not hasattr(getattr(node.bmc, name), "__call__"))):
                    raise AttributeError(
                        "'CompositeBMC' object has no attribute '%s'"
                        % name
                    )

            def function(*args, **kwargs):
                """ Run the named BMC command in parallel across all nodes. """
                tasks = {}
                for node_id, node in nodes.iteritems():
                    tasks[node_id] = task_queue.put(
                        getattr(node.bmc, name),
                        *args,
                        **kwargs
                    )

                results = {}
                errors = {}
                for node_id, task in tasks.items():
                    task.join()
                    if task.status == "Completed":
                        results[node_id] = task.result
                    else:
                        errors[node_id] = task.error
                if errors:
                    raise CommandFailedError(results, errors)
                return results

            return function

    # pylint: disable=R0913
    def __init__(self, ip_address, username="admin", password="admin",
                  tftp=None, ecme_tftp_port=5001, task_queue=None,
                  verbose=False, node=None):
        """Default constructor for the Fabric class."""
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self._tftp = tftp
        self.ecme_tftp_port = ecme_tftp_port
        self.task_queue = task_queue
        self.verbose = verbose
        self.node = node
        self.cbmc = Fabric.CompositeBMC(self)

        self._nodes = {}

        if (not self.node):
            self.node = NODE

        if (not self.task_queue):
            self.task_queue = DEFAULT_TASK_QUEUE

    def __eq__(self, other):
        """__eq__() override."""
        return (isinstance(other, Fabric) and self.nodes == other.nodes)

    def __hash__(self):
        """__hash__() override."""
        return hash(tuple(self.nodes.iteritems()))

    def __str__(self):
        """__str__() override."""
        return 'Fabric Node 0: %s (%d nodes)' % (self.nodes[0].ip_address,
                                                 len(self.nodes))

    @property
    def tftp(self):
        """Returns the tftp server for this Fabric.

        >>> fabric.tftp
        <cxmanage_api.tftp.InternalTftp object at 0x7f5ebbd20b10>

        :return: The tftp server.
        :rtype: `Tftp <tftp.html>`_

        """
        if (not self._tftp):
            self._tftp = InternalTftp.default()

        return self._tftp

    @tftp.setter
    def tftp(self, value):
        """ Set the TFTP server for this fabric (and all nodes) """
        self._tftp = value

        if not self._nodes:
            return

        for node in self.nodes.values():
            node.tftp = value

    @property
    def nodes(self):
        """List of nodes in this fabric.

        >>> fabric.nodes
        {
         0: <cxmanage_api.node.Node object at 0x2052710>,
         1: <cxmanage_api.node.Node object at 0x2052790>,
         2: <cxmanage_api.node.Node object at 0x2052850>,
         3: <cxmanage_api.node.Node object at 0x2052910>
        }

        .. note::
            * Fabric nodes are lazily initialized.

        :returns: A mapping of node ids to node objects.
        :rtype: dictionary

        """
        if not self._nodes:
            self.refresh()

        return self._nodes

    @property
    def primary_node(self):
        """The node to use for fabric config operations.

        Today, this is always node 0.

        >>> fabric.primary_node
        <cxmanage_api.node.Node object at 0x210d790>

        :return: Node object for primary node
        :rtype: Node object
        """
        return self.nodes[0]

    def refresh(self):
        """Gets the nodes of this fabric by pulling IP info from a BMC."""
        self._nodes = {}
        node = self.node(ip_address=self.ip_address, username=self.username,
                         password=self.password, tftp=self.tftp,
                         ecme_tftp_port=self.ecme_tftp_port,
                         verbose=self.verbose)
        ipinfo = node.get_fabric_ipinfo()
        for node_id, node_address in ipinfo.iteritems():
            self._nodes[node_id] = self.node(ip_address=node_address,
                                            username=self.username,
                                            password=self.password,
                                            tftp=self.tftp,
                                            ecme_tftp_port=self.ecme_tftp_port,
                                            verbose=self.verbose)
            self._nodes[node_id].node_id = node_id

    def get_mac_addresses(self):
        """Gets MAC addresses from all nodes.

        >>> fabric.get_mac_addresses()
        {
         0: ['fc:2f:40:3b:ec:40', 'fc:2f:40:3b:ec:41', 'fc:2f:40:3b:ec:42'],
         1: ['fc:2f:40:91:dc:40', 'fc:2f:40:91:dc:41', 'fc:2f:40:91:dc:42'],
         2: ['fc:2f:40:ab:f7:14', 'fc:2f:40:ab:f7:15', 'fc:2f:40:ab:f7:16'],
         3: ['fc:2f:40:88:b3:6c', 'fc:2f:40:88:b3:6d', 'fc:2f:40:88:b3:6e']
        }

        :return: The MAC addresses for each node.
        :rtype: dictionary

        """
        return self.primary_node.get_fabric_macaddrs()

    def get_uplink_info(self, async=False):
        """Gets the fabric uplink info.

        >>> fabric.get_uplink_info()
        {0: 'Node 0: eth0 0, eth1 0, mgmt 0',
         1: 'Node 1: eth0 0, eth1 0, mgmt 0',
         2: 'Node 2: eth0 0, eth1 0, mgmt 0',
         3: 'Node 3: eth0 0, eth1 0, mgmt 0'}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :return: The uplink info for each node.
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_uplink_info")

    def get_uplink_speed(self, async=False):
        """Gets the uplink speed of every node in the fabric.

        >>> fabric.get_uplink_speed()
        {0: 1, 1: 0, 2: 0, 3: 0}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :return: The uplink info for each node.
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_uplink_speed")

    def get_power(self, async=False):
        """Returns the power status for all nodes.

        >>> fabric.get_power()
        {0: False, 1: False, 2: False, 3: False}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (for cmd status, etc.).
        :type async: boolean

        :return: The power status of each node.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_power")

    def set_power(self, mode, async=False, ignore_existing_state=False):
        """Send an IPMI power command to all nodes.

        >>> # On ...
        >>> fabric.set_power(mode='on')
        >>> # Off ...
        >>> fabric.set_power(mode='off')
        >>> # Sanity check ...
        >>> fabric.get_power()
        {0: False, 1: False, 2: False, 3: False}

        :param mode: Mode to set the power to (for all nodes).
        :type mode: string
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean
        :param ignore_existing_state: Flag that allows the caller to only try
                                      to turn on or off nodes that are not
                                      turned on or off, respectively.
        :type ignore_existing_state: boolean

        """
        self._run_on_all_nodes(async, "set_power", mode, ignore_existing_state)

    def get_power_policy(self, async=False):
        """Gets the power policy from all nodes.

        >>> fabric.get_power_policy()
        {0: 'always-on', 1: 'always-on', 2: 'always-on', 3: 'always-on'}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :return: The power policy for all nodes on this fabric.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_power_policy")

    def set_power_policy(self, state, async=False):
        """Sets the power policy on all nodes.

        >>> fabric.set_power_policy(state='always-off')
        >>> # Check to see if it took ...
        >>> fabric.get_power_policy()
        {0: 'always-off', 1: 'always-off', 2: 'always-off', 3: 'always-off'}

        :param state: State to set the power policy to for all nodes.
        :type state: string
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        """
        self._run_on_all_nodes(async, "set_power_policy", state)

    def mc_reset(self, wait=False, async=False):
        """Resets the management controller on all nodes.

        >>> fabric.mc_reset()

        :param wait: Wait for the nodes to come back up.
        :type wait: boolean

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        """
        self._run_on_all_nodes(async, "mc_reset", wait)

    def get_sensors(self, search="", async=False):
        """Gets sensors from all nodes.

        >>> fabric.get_sensors()
        {
         0: {
             'DRAM VDD Current' : <pyipmi.sdr.AnalogSdr object at 0x1a1eb50>,
             'DRAM VDD Voltage' : <pyipmi.sdr.AnalogSdr object at 0x1a1ef10>,
             'MP Temp 0'        : <pyipmi.sdr.AnalogSdr object at 0x1a1ec90>,
             'Node Power'       : <pyipmi.sdr.AnalogSdr object at 0x1a1ed90>,
             'TOP Temp 0'       : <pyipmi.sdr.AnalogSdr object at 0x1a1ecd0>,
             'TOP Temp 1'       : <pyipmi.sdr.AnalogSdr object at 0x1a1ed50>,
             'TOP Temp 2'       : <pyipmi.sdr.AnalogSdr object at 0x1a1edd0>,
             'Temp 0'           : <pyipmi.sdr.AnalogSdr object at 0x1a1ead0>,
             'Temp 1'           : <pyipmi.sdr.AnalogSdr object at 0x1a1ebd0>,
             'Temp 2'           : <pyipmi.sdr.AnalogSdr object at 0x1a1ec10>,
             'Temp 3'           : <pyipmi.sdr.AnalogSdr object at 0x1a1ec50>,
             'V09 Current'      : <pyipmi.sdr.AnalogSdr object at 0x1a1ef90>,
             'V09 Voltage'      : <pyipmi.sdr.AnalogSdr object at 0x1a1ee90>,
             'V18 Current'      : <pyipmi.sdr.AnalogSdr object at 0x1a1ef50>,
             'V18 Voltage'      : <pyipmi.sdr.AnalogSdr object at 0x1a1ee50>,
             'VCORE Current'    : <pyipmi.sdr.AnalogSdr object at 0x1a1efd0>,
             'VCORE Power'      : <pyipmi.sdr.AnalogSdr object at 0x1a1ee10>,
             'VCORE Voltage'    : <pyipmi.sdr.AnalogSdr object at 0x1a1eed0>
            },
            #
            # Output trimmed for brevity ... The output would be the same
            # (format) for the remaining 3 ECMEs on this system.
            #
        },

        .. note::
            * Output condensed for brevity.
            * If the name parameter is not specified, all sensors are returned.

        :param name: Name of the sensor to get. (for all nodes)
        :type name: string
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        """
        return self._run_on_all_nodes(async, "get_sensors", search)

    def get_firmware_info(self, async=False):
        """Gets the firmware info from all nodes.

        >>> fabric.get_firmware_info()
        {
         0: [<pyipmi.fw.FWInfo object at 0x2808110>, ...],
         1: [<pyipmi.fw.FWInfo object at 0x28080d0>, ...],
         2: [<pyipmi.fw.FWInfo object at 0x2808090>, ...],
         3: [<pyipmi.fw.FWInfo object at 0x7f35540660d0>, ...]
        }

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :return: THe firmware info for all nodes.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_firmware_info")

    def get_firmware_info_dict(self, async=False):
        """Gets the firmware info from all nodes.

        >>> fabric.get_firmware_info_dict()
        {0:
           [
            #
            # Each dictionary (in order) in this list represents the
            # corresponding partition information
            #
             {# Partition 0
              'daddr'     : '20029000',
              'flags'     : 'fffffffd',
              'in_use'    : 'Unknown',
              'offset'    : '00000000',
              'partition' : '00',
              'priority'  : '0000000c',
              'size'      : '00005000',
              'type'      : '02 (S2_ELF)',
              'version'   : 'v0.9.1'
             },
             # Partitions 1 - 17
           ],
         #
         # Output trimmed for brevity ... The remaining Nodes in the Fabric
         # would display all the partition format in the same manner.
         #
        }

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :return: The firmware info for all nodes.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_firmware_info_dict")

    def is_updatable(self, package, partition_arg="INACTIVE", priority=None,
                       async=False):
        """Checks to see if all nodes can be updated with this fw package.

        >>> fabric.is_updatable(package=fwpkg)
        {0: True, 1: True, 2: True, 3: True}

        :param package: Firmware package to test for updating.
        :type package: `FirmwarePackage <firmware_package.html>`_
        :param partition: Partition to test for updating.
        :type partition: string
        :param priority: SIMG Header priority.
        :type priority: integer
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :return: Whether or not a node can be updated with the specified
                 firmware package.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "is_updatable", package,
                                 partition_arg, priority)

    def update_firmware(self, package, partition_arg="INACTIVE",
                          priority=None, async=False):
        """Updates the firmware on all nodes.

        >>> fabric.update_firmware(package=fwpkg)

        :param package: Firmware package to update to.
        :type package: `FirmwarePackage <firmware_package.html>`_
        :param partition_arg: Which partition to update.
        :type partition_arg: string
        :param priority: SIMG header Priority setting.
        :type priority: integer
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean
        """
        self._run_on_all_nodes(async, "update_firmware", package,
                          partition_arg, priority)

    def config_reset(self, async=False):
        """Resets the configuration on all nodes to factory defaults.

        >>> fabric.config_reset()
        {0: None, 1: None, 2: None, 3: None}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        """
        self._run_on_all_nodes(async, "config_reset")

    def set_boot_order(self, boot_args, async=False):
        """Sets the boot order on all nodes.

        >>> fabric.set_boot_order(boot_args=['pxe', 'disk'])

        :param boot_args: Boot order list.
        :type boot_args: list
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        """
        self._run_on_all_nodes(async, "set_boot_order", boot_args)

    def get_boot_order(self, async=False):
        """Gets the boot order from all nodes.

        >>> fabric.get_boot_order()
        {
         0: ['disk', 'pxe'],
         1: ['disk', 'pxe'],
         2: ['disk', 'pxe'],
         3: ['disk', 'pxe']
        }

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :returns: The boot order of each node on this fabric.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_boot_order")

    def set_pxe_interface(self, interface, async=False):
        """Sets the pxe interface on all nodes.

        >>> fabric.set_pxe_interface(interface='eth0')

        :param interface: Inteface for pxe requests
        :type interface: string
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        """
        self._run_on_all_nodes(async, "set_pxe_interface", interface)

    def get_pxe_interface(self, async=False):
        """Gets the pxe interface from all nodes.

        >>> fabric.get_pxe_interface()
        {
         0: 'eth0',
         1: 'eth0',
         2: 'eth0',
         3: 'eth0'
        }

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :returns: The boot order of each node on this fabric.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_pxe_interface")

    def get_versions(self, async=False):
        """Gets the version info from all nodes.

        >>> fabric.get_versions()
        {
         0: <pyipmi.info.InfoBasicResult object at 0x1f74150>,
         1: <pyipmi.info.InfoBasicResult object at 0x1f745d0>,
         2: <pyipmi.info.InfoBasicResult object at 0x1f743d0>,
         3: <pyipmi.info.InfoBasicResult object at 0x1f74650>
        }

        .. seealso::
            `Node.get_versions() \
<node.html#cxmanage_api.node.Node.get_versions>`_

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Command object (can get status, etc.).
        :type async: boolean

        :returns: The basic SoC info for all nodes.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_versions")

    def get_versions_dict(self, async=False):
        """Gets the version info from all nodes.

        >>> fabric.get_versions_dict()
        {0:
            {
             'a9boot_version'   : 'v2012.10.16',
             'bootlog_version'  : 'v0.9.1-39-g7e10987',
             'build_number'     : '7E10987C',
             'card'             : 'EnergyCard X02',
             'cdb_version'      : 'v0.9.1-39-g7e10987',
             'dtb_version'      : 'v3.6-rc1_cx_2012.10.02',
             'header'           : 'Calxeda SoC (0x0096CD)',
             'soc_version'      : 'v0.9.1',
             'stage2_version'   : 'v0.9.1',
             'timestamp'        : '1352911670',
             'uboot_version'    : 'v2012.07_cx_2012.10.29',
             'ubootenv_version' : 'v2012.07_cx_2012.10.29',
             'version'          : 'ECX-1000-v1.7.1'
            },
         #
         # Output trimmed for brevity ... Each remaining Nodes get_versions
         # dictionary would be printed.
         #
        }

        .. seealso::
            `Node.get_versions_dict() \
<node.html#cxmanage_api.node.Node.get_versions_dict>`_

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The basic SoC info for all nodes.
        :rtype: dictionary or `Task <tasks.html>`__

        """
        return self._run_on_all_nodes(async, "get_versions_dict")

    def ipmitool_command(self, ipmitool_args, asynchronous=False):
        """Run an arbitrary IPMItool command on all nodes.

        >>> # Gets eth0's MAC Address for each node ...
        >>> fabric.ipmitool_command(['cxoem', 'fabric', 'get', 'macaddr',
        >>> ...'interface', '0'])
        {
         0: 'fc:2f:40:3b:ec:40',
         1: 'fc:2f:40:91:dc:40',
         2: 'fc:2f:40:ab:f7:14',
         3: 'fc:2f:40:88:b3:6c'
        }

        :param ipmitool_args: Arguments to pass on to the ipmitool command.
        :type ipmitool_args: list
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: IPMI command response.
        :rtype: string

        """
        return self._run_on_all_nodes(asynchronous, "ipmitool_command",
                                 ipmitool_args)

    def get_ubootenv(self, async=False):
        """Gets the u-boot environment from all nodes.

        >>> fabric.get_ubootenv()
        {
         0: <cxmanage_api.ubootenv.UbootEnv instance at 0x7fc2d4058098>,
         1: <cxmanage_api.ubootenv.UbootEnv instance at 0x7fc2d4058908>,
         2: <cxmanage_api.ubootenv.UbootEnv instance at 0x7fc2d40582d8>,
         3: <cxmanage_api.ubootenv.UbootEnv instance at 0x7fc2d40589e0>
        }

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: UBootEnvironment objects for all nodes.
        :rtype: dictionary or `Task <command.html>`_

        """
        return self._run_on_all_nodes(async, "get_ubootenv")

    # pylint: disable=R0913
    def get_server_ip(self, interface=None, ipv6=False, user="user1",
            password="1Password", aggressive=False, async=False):
        """Get the server IP address from all nodes. The nodes must be powered
        on for this to work.

        >>> fabric.get_server_ip()
        {
         0: '192.168.100.100',
         1: '192.168.100.101',
         2: '192.168.100.102',
         3: '192.168.100.103'
        }

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
        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :return: Server IP addresses for all nodes..
        :rtype: dictionary or `Task <command.html>`_

        """
        return self._run_on_all_nodes(async, "get_server_ip", interface, ipv6,
                user, password, aggressive)

    def get_ipsrc(self):
        """Return the ipsrc for the fabric.

        >>> fabric.get_ipsrc()
        2

        :return: 1 for static, 2 for DHCP
        :rtype: integer
        """
        return self.primary_node.bmc.fabric_config_get_ip_src()

    def set_ipsrc(self, ipsrc_mode):
        """Set the ipsrc for the fabric.

        >>> fabric.set_ipsrc(2)

        :param ipsrc_mode: 1 for static, 2 for DHCP
        :type ipsrc_mode: integer
        """
        self.primary_node.bmc.fabric_config_set_ip_src(ipsrc_mode)

    def apply_factory_default_config(self):
        """Sets the fabric config to factory default

        >>> fabric.apply_factory_default_config()
        """
        self.primary_node.bmc.fabric_config_factory_default()

    def get_ipaddr_base(self):
        """The base IPv4 address for a range of static IP addresses used
        for the nodes in the fabric

        >>> fabric.get_ipaddr_base()
        '192.168.100.1'

        :return: The first IP address in the range of static IP addresses
        :rtype: string
        """
        return self.primary_node.bmc.fabric_config_get_ip_addr_base()

    def update_config(self):
        """Push out updated configuration data for all nodes in the fabric.

        >>> fabric.update_config()

        """
        self.primary_node.bmc.fabric_config_update_config()

    def get_linkspeed(self):
        """Get the global linkspeed for the fabric. In the partition world
        this means the linkspeed for Configuration 0, Partition 0, Profile 0.

        >>> fabric.get_linkspeed()
        2.5

        :return: Linkspeed for the fabric.
        :rtype: float

        """
        return self.primary_node.bmc.fabric_config_get_linkspeed()

    def set_linkspeed(self, linkspeed):
        """Set the global linkspeed for the fabric. In the partition world
        this means the linkspeed for Configuration 0, Partition 0, Profile 0.

        >>> fabric.set_linkspeed(10)

        :param linkspeed: Linkspeed specified in Gbps.
        :type linkspeed: float

        """
        self.primary_node.bmc.fabric_config_set_linkspeed(linkspeed)

    def add_macaddr(self, nodeid, iface, macaddr):
        """Add a new macaddr to a node/interface in the fabric.

        >>> fabric.add_macaddr(3, 1, "66:55:44:33:22:11")

        :param nodeid: Node id to which the macaddr is to be added
        :type nodeid: integer
        :param iface: interface on the node to which the macaddr is to be added
        :type iface: integer
        :param macaddr: mac address to be added
        :type macaddr: string

        """
        self.primary_node.bmc.fabric_add_macaddr(nodeid=nodeid, iface=iface,
                macaddr=macaddr)

    def rm_macaddr(self, nodeid, iface, macaddr):
        """Remove a macaddr to a node/interface in the fabric.

        >>> fabric.rm_macaddr(3, 1, "66:55:44:33:22:11")

        :param nodeid: Node id from which the macaddr is to be remove
        :type nodeid: integer
        :param iface: interface on the node which the macaddr is to be removed
        :type iface: integer
        :param macaddr: mac address to be removed
        :type macaddr: string

        """
        self.primary_node.bmc.fabric_rm_macaddr(nodeid=nodeid, iface=iface,
                macaddr=macaddr)

    def set_macaddr_base(self, macaddr):
        """ Set a base MAC address for a custom range.

        >>> fabric.set_macaddr_base("66:55:44:33:22:11")

        :param macaddr: mac address base to use
        :type macaddr: string

        """
        self.primary_node.bmc.fabric_config_set_macaddr_base(macaddr=macaddr)

    def get_macaddr_base(self):
        """ Get the base MAC address for custom ranges.

        >>> fabric.get_macaddr_base()
        '08:00:00:00:08:5c'

        :return: mac address base
        :rtype: string
        """
        return self.primary_node.bmc.fabric_config_get_macaddr_base()

    def set_macaddr_mask(self, mask):
        """ Set MAC address mask for a custom range.

        >>> fabric.set_macaddr_mask("ff:ff:ff:ff:ff:00")

        :param macaddr: mac address mask to use
        :type macaddr: string

        """
        self.primary_node.bmc.fabric_config_set_macaddr_mask(mask=mask)

    def get_macaddr_mask(self):
        """ Get the MAC address mask for custom ranges.

        >>> fabric.get_macaddr_mask()
        '08:00:00:00:08:5c'

        :return: mac address mask
        :rtype: string

        """
        return self.primary_node.bmc.fabric_config_get_macaddr_mask()

    def get_linkspeed_policy(self):
        """Get the global linkspeed policy for the fabric. In the partition
        world this means the linkspeed for Configuration 0, Partition 0,
        Profile 0.

        >>> fabric.get_linkspeed_policy()
        1

        :return: Linkspeed Policy for the fabric.
        :rtype: integer

        """
        return self.primary_node.bmc.fabric_config_get_linkspeed_policy()

    def set_linkspeed_policy(self, ls_policy):
        """Set the global linkspeed policy for the fabric. In the partition
        world this means the linkspeed policy for Configuration 0,
        Partition 0, Profile 0.

        >>> fabric.set_linkspeed_policy(1)

        :param linkspeed: Linkspeed Policy. 0: Fixed, 1: Topological
        :type linkspeed: integer

        """
        self.primary_node.bmc.fabric_config_set_linkspeed_policy(ls_policy)

    def get_link_users_factor(self):
        """Get the global link users factor for the fabric. In the partition
        world this means the link users factor for Configuration 0,
        Partition 0, Profile 0.

        >>> fabric.get_link_users_factor()
        1

        :return: Link users factor for the fabric.
        :rtype: integer

        """
        return self.primary_node.bmc.fabric_config_get_link_users_factor()

    def set_link_users_factor(self, lu_factor):
        """Set the global link users factor for the fabric. In the partition
        world this means the link users factor for Configuration 0,
        Partition 0, Profile 0.

        >>> fabric.set_link_users_factor(10)

        :param lu_factor: Multiplying factor for topological linkspeeds
        :type lu_factor: integer

        """
        self.primary_node.bmc.fabric_config_set_link_users_factor(lu_factor)

    def get_uplink(self, iface=0):
        """Get the uplink for an interface to xmit a packet out of the cluster.

        >>> fabric.get_uplink(0)
        0

        :param iface: The interface for the uplink.
        :type iface: integer

        :return: The uplink iface is using.
        :rtype: integer

        """
        return self.primary_node.bmc.fabric_config_get_uplink(iface=iface)

    def set_uplink(self, uplink=0, iface=0):
        """Set the uplink for an interface to xmit a packet out of the cluster.

        >>> fabric.set_uplink(uplink=0,iface=0)

        :param uplink: The uplink to set.
        :type uplink: integer
        :param iface: The interface for the uplink.
        :type iface: integer

        """
        self.primary_node.bmc.fabric_config_set_uplink(uplink=uplink,
                iface=iface)

    def get_link_stats(self, link=0, async=False):
        """Get the link_stats for each node in the fabric.

        >>> fabric.get_link_stats()
        {0: {'FS_LC0_BYTE_CNT_0': '0x0',
          'FS_LC0_BYTE_CNT_1': '0x0',
          'FS_LC0_CFG_0': '0x1000d07f',
          'FS_LC0_CFG_1': '0x105f',
          'FS_LC0_CM_RXDATA_0': '0x0',
          'FS_LC0_CM_RXDATA_1': '0x0',
          'FS_LC0_CM_TXDATA_0': '0x82000002',
          'FS_LC0_CM_TXDATA_1': '0x0',
          'FS_LC0_PKT_CNT_0': '0x0',
          'FS_LC0_PKT_CNT_1': '0x0',
          'FS_LC0_RDRPSCNT': '0x3e89f',
          'FS_LC0_RERRSCNT': '0x0',
          'FS_LC0_RMCSCNT': '0x174b9bf',
          'FS_LC0_RPKTSCNT': '0x0',
          'FS_LC0_RUCSCNT': '0x43e9b',
          'FS_LC0_SC_STAT': '0x0',
          'FS_LC0_STATE': '0x1033',
          'FS_LC0_TDRPSCNT': '0x0',
          'FS_LC0_TPKTSCNT': '0x1'},
         }}
        >>> #
        >>> # Output trimmed for brevity ...
        >>> # The data shown for node 0 is the same type of data for each
        >>> # node in  the fabric.
        >>> #

        :param link: The link to get stats for (0-4).
        :type link: integer

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The link_stats for each link on each node.
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_link_stats", link)

    def get_linkmap(self, async=False):
        """Get the linkmap for each node in the fabric.

        >>> fabric.get_linkmap()
        {0: {1: 2, 3: 1, 4: 3}, 1: {3: 0}, 2: {3: 0, 4: 3}, 3: {3: 0, 4: 2}}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The linkmap for each node.
        :rtype: dectionary

        """
        return self._run_on_all_nodes(async, "get_linkmap")

    def get_routing_table(self, async=False):
        """Get the routing_table for the fabric.

        >>> fabric.get_routing_table()
        {0: {1: [0, 0, 0, 3, 0], 2: [0, 3, 0, 0, 2], 3: [0, 2, 0, 0, 3]},
         1: {0: [0, 0, 0, 3, 0], 2: [0, 0, 0, 2, 0], 3: [0, 0, 0, 2, 0]},
         2: {0: [0, 0, 0, 3, 2], 1: [0, 0, 0, 2, 0], 3: [0, 0, 0, 2, 3]},
         3: {0: [0, 0, 0, 3, 2], 1: [0, 0, 0, 2, 0], 2: [0, 0, 0, 2, 3]}}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The routing_table for the fabric.
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_routing_table")

    def get_depth_chart(self, async=False):
        """Get the depth_chart for the fabric.

        >>> fabric.get_depth_chart()
        {0: {1: {'shortest': (0, 0)},
          2: {'others': [(3, 1)], 'shortest': (0, 0)},
          3: {'others': [(2, 1)], 'shortest': (0, 0)}},
         1: {0: {'shortest': (1, 0)},
          2: {'others': [(3, 2)], 'shortest': (0, 1)},
          3: {'others': [(2, 2)], 'shortest': (0, 1)}},
         2: {0: {'others': [(3, 1)], 'shortest': (2, 0)},
          1: {'shortest': (0, 1)},
          3: {'others': [(0, 1)], 'shortest': (2, 0)}},
         3: {0: {'others': [(2, 1)], 'shortest': (3, 0)},
          1: {'shortest': (0, 1)},
          2: {'others': [(0, 1)], 'shortest': (3, 0)}}}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The depth_chart for the fabric.
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_depth_chart")

    def get_node_fru_version(self, async=False):
        """Get each node's node FRU version.

        >>> fabric.get_node_fru_version()
        {0: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c',
         1: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c',
         2: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c',
         3: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c'}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The node FRU versions for each node in the fabric
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_node_fru_version")

    def get_slot_fru_version(self, async=False):
        """Get each node's slot FRU version.

        >>> fabric.get_slot_fru_version()
        {0: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c',
         1: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c',
         2: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c',
         3: 'bf7b471716113d5b9c47c6a5dd25f7a83f5c235c'}

        :param async: Flag that determines if the command result (dictionary)
                      is returned or a Task object (can get status, etc.).
        :type async: boolean

        :returns: The slot FRU versions for each node in the fabric
        :rtype: dictionary

        """
        return self._run_on_all_nodes(async, "get_slot_fru_version")

    def _run_on_all_nodes(self, async, name, *args, **kwargs):
        """Start a command on all nodes."""
        tasks = {}
        for node_id, node in self.nodes.iteritems():
            tasks[node_id] = self.task_queue.put(getattr(node, name), *args,
                                                 **kwargs)

        if async:
            return tasks
        else:
            results = {}
            errors = {}
            for node_id, task in tasks.iteritems():
                task.join()
                if task.status == "Completed":
                    results[node_id] = task.result
                else:
                    errors[node_id] = task.error
            if errors:
                raise CommandFailedError(results, errors)
            return results


# End of file: ./fabric.py
