# pylint: disable=C0302
"""Unit tests for the Node class."""


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


import random
import shutil
import tempfile
import unittest

from pyipmi import IpmiError
from pyipmi.bmc import LanBMC

from cxmanage_test import TestImage, TestSensor, random_file
from cxmanage_api import temp_file
from cxmanage_api.simg import create_simg, get_simg_header
from cxmanage_api.node import Node
from cxmanage_api.tftp import InternalTftp, ExternalTftp
from cxmanage_api.ubootenv import UbootEnv
from cxmanage_api.firmware_package import FirmwarePackage
from cxmanage_api.cx_exceptions import IPDiscoveryError


NUM_NODES = 4
ADDRESSES = ["192.168.100.%i" % n for n in range(1, NUM_NODES + 1)]
TFTP = InternalTftp()


# pylint: disable=R0904, W0201
class NodeTest(unittest.TestCase):
    """ Tests involving cxmanage Nodes """

    def setUp(self):
        self.nodes = [Node(ip_address=ip, tftp=TFTP, bmc=DummyBMC,
                image=TestImage, ubootenv=DummyUbootEnv,
                ipretriever=DummyIPRetriever, verbose=True)
                for ip in ADDRESSES]

        self.server_ip = None
        self.fabric_ipsrc = None
        self.fabric_ls_policy = None
        self.fabric_linkspeed = None
        self.fabric_lu_factor = None

        # Give each node a node_id
        count = 0
        for node in self.nodes:
            node.node_id = count
            count = count + 1

        # Set up an internal server
        self.work_dir = tempfile.mkdtemp(prefix="cxmanage_node_test-")

    def tearDown(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def test_get_power(self):
        """ Test node.get_power method """
        for node in self.nodes:
            result = node.get_power()

            self.assertEqual(node.bmc.executed, ["get_chassis_status"])
            self.assertEqual(result, False)

    def test_set_power(self):
        """ Test node.set_power method """
        for node in self.nodes:
            modes = ["off", "on", "reset", "off"]
            for mode in modes:
                node.set_power(mode)

            self.assertEqual(node.bmc.executed,
                    [("set_chassis_power", x) for x in modes])

    def test_get_power_policy(self):
        """ Test node.get_power_policy method """
        for node in self.nodes:
            result = node.get_power_policy()

            self.assertEqual(node.bmc.executed, ["get_chassis_status"])
            self.assertEqual(result, "always-off")

    def test_set_power_policy(self):
        """ Test node.set_power_policy method """
        for node in self.nodes:
            modes = ["always-on", "previous", "always-off"]
            for mode in modes:
                node.set_power_policy(mode)

            self.assertEqual(node.bmc.executed,
                    [("set_chassis_policy", x) for x in modes])

    def test_get_sensors(self):
        """ Test node.get_sensors method """
        for node in self.nodes:
            result = node.get_sensors()

            self.assertEqual(node.bmc.executed, ["sdr_list"])

            self.assertEqual(len(result), 2)
            self.assertTrue(
                result["Node Power"].sensor_reading.endswith("Watts")
            )
            self.assertTrue(
                result["Board Temp"].sensor_reading.endswith("degrees C")
            )

    def test_is_updatable(self):
        """ Test node.is_updatable method """
        for node in self.nodes:
            max_size = 12288 - 60
            filename = random_file(max_size)
            images = [
                TestImage(filename, "SOC_ELF"),
                TestImage(filename, "CDB"),
                TestImage(filename, "UBOOTENV")
            ]

            # should pass
            package = FirmwarePackage()
            package.images = images
            self.assertTrue(node.is_updatable(package))

            # should fail if the firmware version is wrong
            package = FirmwarePackage()
            package.images = images
            package.version = "ECX-31415-v0.0.0"
            self.assertFalse(node.is_updatable(package))

            # should fail if we specify a socman version
            package = FirmwarePackage()
            package.images = images
            package.required_socman_version = "0.0.1"
            self.assertFalse(node.is_updatable(package))

            # should fail if we try to upload a slot2
            package = FirmwarePackage()
            package.images = images
            package.config = "slot2"
            self.assertFalse(node.is_updatable(package))

            # should fail if we upload an image that's too large
            package = FirmwarePackage()
            package.images = [TestImage(random_file(max_size + 1), "UBOOTENV")]
            self.assertFalse(node.is_updatable(package))

            # should fail if we upload to a CDB partition that's in use
            package = FirmwarePackage()
            package.images = images
            self.assertFalse(node.is_updatable(package, partition_arg="ACTIVE"))

    def test_update_firmware(self):
        """ Test node.update_firmware method """
        filename = "%s/%s" % (self.work_dir, "image.bin")
        open(filename, "w").write("")

        package = FirmwarePackage()
        package.images = [
            TestImage(filename, "SOC_ELF"),
            TestImage(filename, "CDB"),
            TestImage(filename, "UBOOTENV")
        ]
        package.version = "0.0.1"

        for node in self.nodes:
            node.update_firmware(package)

            partitions = node.bmc.partitions
            unchanged_partitions = [partitions[x] for x in [0, 1, 4]]
            changed_partitions = [partitions[x] for x in [2, 3, 6]]
            ubootenv_partition = partitions[5]

            for partition in unchanged_partitions:
                self.assertEqual(partition.updates, 0)
                self.assertEqual(partition.retrieves, 0)
                self.assertEqual(partition.checks, 0)
                self.assertEqual(partition.activates, 0)

            for partition in changed_partitions:
                self.assertEqual(partition.updates, 1)
                self.assertEqual(partition.retrieves, 0)
                self.assertEqual(partition.checks, 2)
                self.assertEqual(partition.activates, 1)

            self.assertEqual(ubootenv_partition.updates, 1)
            self.assertEqual(ubootenv_partition.retrieves, 1)
            self.assertEqual(ubootenv_partition.checks, 2)
            self.assertEqual(ubootenv_partition.activates, 1)

            self.assertTrue(("set_firmware_version", "0.0.1")
                    in node.bmc.executed)

    def test_config_reset(self):
        """ Test node.config_reset method """
        for node in self.nodes:
            node.config_reset()

            # Assert config reset
            executed = node.bmc.executed
            self.assertEqual(
                    len([x for x in executed if x == "reset_firmware"]), 1)

            # Assert sel clear
            self.assertEqual(
                    len([x for x in executed if x == "sel_clear"]), 1)

            # Assert ubootenv changes
            active = node.bmc.partitions[5]
            inactive = node.bmc.partitions[6]
            self.assertEqual(active.updates, 1)
            self.assertEqual(active.retrieves, 0)
            self.assertEqual(active.checks, 1)
            self.assertEqual(active.activates, 1)
            self.assertEqual(inactive.updates, 0)
            self.assertEqual(inactive.retrieves, 1)
            self.assertEqual(inactive.checks, 0)
            self.assertEqual(inactive.activates, 0)

    def test_set_boot_order(self):
        """ Test node.set_boot_order method """
        boot_args = ["disk", "pxe", "retry"]
        for node in self.nodes:
            node.set_boot_order(boot_args)

            partitions = node.bmc.partitions
            ubootenv_partition = partitions[5]
            unchanged_partitions = [x for x in partitions
                    if x != ubootenv_partition]

            self.assertEqual(ubootenv_partition.updates, 1)
            self.assertEqual(ubootenv_partition.retrieves, 1)
            self.assertEqual(ubootenv_partition.checks, 1)
            self.assertEqual(ubootenv_partition.activates, 1)

            for partition in unchanged_partitions:
                self.assertEqual(partition.updates, 0)
                self.assertEqual(partition.retrieves, 0)
                self.assertEqual(partition.checks, 0)
                self.assertEqual(partition.activates, 0)

    def test_get_boot_order(self):
        """ Test node.get_boot_order method """
        for node in self.nodes:
            result = node.get_boot_order()

            partitions = node.bmc.partitions
            ubootenv_partition = partitions[5]
            unchanged_partitions = [x for x in partitions
                    if x != ubootenv_partition]

            self.assertEqual(ubootenv_partition.updates, 0)
            self.assertEqual(ubootenv_partition.retrieves, 1)
            self.assertEqual(ubootenv_partition.checks, 0)
            self.assertEqual(ubootenv_partition.activates, 0)

            for partition in unchanged_partitions:
                self.assertEqual(partition.updates, 0)
                self.assertEqual(partition.retrieves, 0)
                self.assertEqual(partition.checks, 0)
                self.assertEqual(partition.activates, 0)

            self.assertEqual(result, ["disk", "pxe"])

    def test_set_pxe_interface(self):
        """ Test node.set_pxe_interface method """
        for node in self.nodes:
            node.set_pxe_interface("eth0")

            partitions = node.bmc.partitions
            ubootenv_partition = partitions[5]
            unchanged_partitions = [x for x in partitions
                    if x != ubootenv_partition]

            self.assertEqual(ubootenv_partition.updates, 1)
            self.assertEqual(ubootenv_partition.retrieves, 1)
            self.assertEqual(ubootenv_partition.checks, 1)
            self.assertEqual(ubootenv_partition.activates, 1)

            for partition in unchanged_partitions:
                self.assertEqual(partition.updates, 0)
                self.assertEqual(partition.retrieves, 0)
                self.assertEqual(partition.checks, 0)
                self.assertEqual(partition.activates, 0)

    def test_get_pxe_interface(self):
        """ Test node.get_pxe_interface method """
        for node in self.nodes:
            result = node.get_pxe_interface()

            partitions = node.bmc.partitions
            ubootenv_partition = partitions[5]
            unchanged_partitions = [x for x in partitions
                    if x != ubootenv_partition]

            self.assertEqual(ubootenv_partition.updates, 0)
            self.assertEqual(ubootenv_partition.retrieves, 1)
            self.assertEqual(ubootenv_partition.checks, 0)
            self.assertEqual(ubootenv_partition.activates, 0)

            for partition in unchanged_partitions:
                self.assertEqual(partition.updates, 0)
                self.assertEqual(partition.retrieves, 0)
                self.assertEqual(partition.checks, 0)
                self.assertEqual(partition.activates, 0)

            self.assertEqual(result, "eth0")

    def test_get_versions(self):
        """ Test node.get_versions method """
        for node in self.nodes:
            result = node.get_versions()

            self.assertEqual(node.bmc.executed, ["get_info_basic",
                    "get_firmware_info", "info_card"])
            for attr in ["iana", "firmware_version", "ecme_version",
                    "ecme_timestamp"]:
                self.assertTrue(hasattr(result, attr))

    def test_get_fabric_ipinfo(self):
        """ Test node.get_fabric_ipinfo method """
        for node in self.nodes:
            result = node.get_fabric_ipinfo()

            for found in node.bmc.executed:
                self.assertEqual(found, "fabric_config_get_ip_info")

            self.assertEqual(result, dict([(i, ADDRESSES[i])
                    for i in range(NUM_NODES)]))

    def test_get_fabric_macaddrs(self):
        """ Test node.get_fabric_macaddrs method """
        for node in self.nodes:
            result = node.get_fabric_macaddrs()

            for found in node.bmc.executed:
                self.assertEqual(found, "fabric_config_get_mac_addresses")

            self.assertEqual(len(result), NUM_NODES)
            for node_id in xrange(NUM_NODES):
                self.assertEqual(len(result[node_id]), 3)
                for port in result[node_id]:
                    expected_macaddr = "00:00:00:00:%x:%x" % (node_id, port)
                    self.assertEqual(result[node_id][port], [expected_macaddr])

    def test_get_fabric_uplink_info(self):
        """ Test node.get_fabric_uplink_info method """
        for node in self.nodes:
            node.get_fabric_uplink_info()

            for found in node.bmc.executed:
                self.assertEqual(found, "fabric_config_get_uplink_info")

    def test_get_uplink_info(self):
        """ Test node.get_uplink_info method """
        for node in self.nodes:
            node.get_uplink_info()

            for found in node.bmc.executed:
                self.assertEqual(found, "get_uplink_info")

    def test_get_uplink_speed(self):
        """ Test node.get_uplink_info method """
        for node in self.nodes:
            node.get_uplink_speed()

            for found in node.bmc.executed:
                self.assertEqual(found, "get_uplink_speed")


    def test_get_linkmap(self):
        """ Test node.get_linkmap method """
        for node in self.nodes:
            node.get_linkmap()

            for found in node.bmc.executed:
                self.assertEqual(found, "fabric_info_get_link_map")

    def test_get_routing_table(self):
        """ Test node.get_routing_table method """
        for node in self.nodes:
            node.get_routing_table()

            for found in node.bmc.executed:
                self.assertEqual(found, "fabric_info_get_routing_table")

    def test_get_depth_chart(self):
        """ Test node.get_depth_chart method """
        for node in self.nodes:
            node.get_depth_chart()

            for found in node.bmc.executed:
                self.assertEqual(found, "fabric_info_get_depth_chart")

    def test_get_link_stats(self):
        """ Test node.get_link_stats() """
        for node in self.nodes:
            node.get_link_stats()
            self.assertEqual(node.bmc.executed[0], ('fabric_get_linkstats', 0))

    def test_get_server_ip(self):
        """ Test node.get_server_ip method """
        for node in self.nodes:
            result = node.get_server_ip()
            self.assertEqual(result, "192.168.200.1")

    def test_get_linkspeed(self):
        """ Test node.get_linkspeed method """
        for node in self.nodes:
            result = node.get_linkspeed()
            self.assertEqual(result, 1)

    def test_get_uplink(self):
        """ Test node.get_uplink method"""
        for node in self.nodes:
            result = node.get_uplink(iface=0)
            self.assertEqual(result, 0)

    def test_set_uplink(self):
        """ Test node.set_uplink method """
        for node in self.nodes:
            node.set_uplink(iface=0, uplink=0)
            self.assertEqual(node.get_uplink(iface=0), 0)

    def test_get_node_fru_version(self):
        """ Test node.get_node_fru_version method """
        for node in self.nodes:
            node.get_node_fru_version()
            self.assertEqual(node.bmc.executed, ['node_fru_read'])

    def test_get_slot_fru_version(self):
        """ Test node.get_slot_fru_version method """
        for node in self.nodes:
            node.get_slot_fru_version()
            self.assertEqual(node.bmc.executed, ['slot_fru_read'])

# pylint: disable=R0902
class DummyBMC(LanBMC):
    """ Dummy BMC for the node tests """


    GUID_UNIQUE = 0


    def __init__(self, **kwargs):
        super(DummyBMC, self).__init__(**kwargs)
        self.executed = []
        self.partitions = [
                Partition(0, 3, 0, 393216, in_use=True),  # socman
                Partition(1, 10, 393216, 196608, in_use=True),  # factory cdb
                Partition(2, 3, 589824, 393216, in_use=False),  # socman
                Partition(3, 10, 983040, 196608, in_use=False),  # factory cdb
                Partition(4, 10, 1179648, 196608, in_use=True),  # running cdb
                Partition(5, 11, 1376256, 12288),  # ubootenv
                Partition(6, 11, 1388544, 12288)  # ubootenv
        ]
        self.ipaddr_base = '192.168.100.1'
        self.unique_guid = 'FAKEGUID%s' % DummyBMC.GUID_UNIQUE
        DummyBMC.GUID_UNIQUE += 1

    def guid(self):
        """Returns the GUID"""
        self.executed.append("guid")

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self, dummybmc):
                self.system_guid = dummybmc.unique_guid
                self.time_stamp = None
        return Result(self)

    def set_chassis_power(self, mode):
        """ Set chassis power """
        self.executed.append(("set_chassis_power", mode))

    def get_chassis_status(self):
        """ Get chassis status """
        self.executed.append("get_chassis_status")

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                self.power_on = False
                self.power_restore_policy = "always-off"
        return Result()

    def set_chassis_policy(self, mode):
        """ Set chassis restore policy """
        self.executed.append(("set_chassis_policy", mode))

    def mc_reset(self, mode):
        """ Reset the MC """
        self.executed.append(("mc_reset", mode))

    def reset_firmware(self):
        """ Reset the running CDB """
        self.executed.append("reset_firmware")

    def sel_clear(self):
        """ Clear SEL """
        self.executed.append("sel_clear")

    def get_firmware_info(self):
        """ Get partition and simg info """
        self.executed.append("get_firmware_info")

        return [x.fwinfo for x in self.partitions]

    def update_firmware(self, filename, partition, image_type, tftp_addr):
        """ Download a file from a TFTP server to a given partition.

        Make sure the image type matches. """
        self.executed.append(("update_firmware", filename,
                partition, image_type, tftp_addr))
        self.partitions[partition].updates += 1

        localfile = temp_file()
        TFTP.get_file(filename, localfile)

        contents = open(localfile).read()
        simg = get_simg_header(contents)
        self.partitions[partition].fwinfo.offset = "%8x" % simg.imgoff
        self.partitions[partition].fwinfo.size = "%8x" % simg.imglen
        self.partitions[partition].fwinfo.priority = "%8x" % simg.priority
        self.partitions[partition].fwinfo.daddr = "%8x" % simg.daddr

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                """Default constructor for the Result class."""
                self.tftp_handle_id = 0
        return Result()

    def retrieve_firmware(self, filename, partition, image_type, tftp_addr):
        self.executed.append(("retrieve_firmware", filename,
                partition, image_type, tftp_addr))
        self.partitions[partition].retrieves += 1

        # Upload blank image to tftp
        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")
        open("%s/%s" % (work_dir, filename), "w").write(create_simg(""))
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)
        shutil.rmtree(work_dir)

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                self.tftp_handle_id = 0
        return Result()

    def register_firmware_read(self, filename, partition, image_type):
        self.executed.append(("register_firmware_read", filename, partition,
                image_type))
        raise IpmiError()

    def register_firmware_write(self, filename, partition, image_type):
        self.executed.append(("register_firmware_write", filename, partition,
                image_type))
        raise IpmiError()

    def get_firmware_status(self, handle):
        self.executed.append("get_firmware_status")

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                self.status = "Complete"

        del handle

        return Result()

    def check_firmware(self, partition):
        self.executed.append(("check_firmware", partition))
        self.partitions[partition].checks += 1

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                self.crc32 = 0
                self.error = None
        return Result()

    def activate_firmware(self, partition):
        self.executed.append(("activate_firmware", partition))
        self.partitions[partition].activates += 1

    def set_firmware_version(self, version):
        self.executed.append(("set_firmware_version", version))

    def sdr_list(self):
        """ Get sensor info from the node. """
        self.executed.append("sdr_list")

        power_value = "%f (+/- 0) Watts" % random.uniform(0, 10)
        temp_value = "%f (+/- 0) degrees C" % random.uniform(30, 50)
        sensors = [
                TestSensor("Node Power", power_value),
                TestSensor("Board Temp", temp_value)
        ]

        return sensors

    def get_info_basic(self):
        """ Get basic SoC info from this node """
        self.executed.append("get_info_basic")

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                self.iana = int("0x0096CD", 16)
                self.firmware_version = "ECX-0000-v0.0.0"
                self.ecme_version = "v0.0.0"
                self.ecme_timestamp = 0
        return Result()

    def get_info_card(self):
        self.executed.append("info_card")

        # pylint: disable=R0903
        class Result(object):
            """Results class."""
            def __init__(self):
                self.type = "TestBoard"
                self.revision = "0"
        return Result()

    node_count = 0
    def fabric_get_node_id(self):
        self.executed.append('get_node_id')
        result = DummyBMC.node_count
        DummyBMC.node_count += 1
        return result

    def fabric_info_get_link_map(self, filename, tftp_addr=None):
        """Upload a link_map file from the node to TFTP"""
        self.executed.append('fabric_info_get_link_map')

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        link_map = []
        link_map.append('Link 1: Node 2')
        link_map.append('Link 3: Node 1')
        link_map.append('Link 4: Node 3')

        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")
        with open('%s/%s' % (work_dir, filename), 'w') as lm_file:
            for lmap in link_map:
                lm_file.write(lmap + '\n')
            lm_file.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    def fabric_info_get_routing_table(self, filename, tftp_addr=None):
        """Upload a routing_table file from the node to TFTP"""
        self.executed.append('fabric_info_get_routing_table')

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        routing_table = []
        routing_table.append('Node 1: rt - 0.2.0.3.2')
        routing_table.append('Node 2: rt - 0.3.0.1.2')
        routing_table.append('Node 3: rt - 0.2.0.1.3')
        routing_table.append('Node 12: rt - 0.2.0.0.1')
        routing_table.append('Node 13: rt - 0.2.0.0.1')
        routing_table.append('Node 14: rt - 0.2.0.0.1')
        routing_table.append('Node 15: rt - 0.2.0.0.1')

        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")
        with open('%s/%s' % (work_dir, filename), 'w') as rt_file:
            for rtable in routing_table:
                rt_file.write(rtable + '\n')
            rt_file.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    def fabric_info_get_depth_chart(self, filename, tftp_addr=None):
        """Upload a depth_chart file from the node to TFTP"""
        self.executed.append('fabric_info_get_depth_chart')

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        depth_chart = []
        depth_chart.append(
           'Node 1: Shortest Distance 0 hops via neighbor 0: ' +
           'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 2: Shortest Distance 0 hops via neighbor 0: ' +
            'other hops/neighbors - 1/3'
        )
        depth_chart.append(
            'Node 3: Shortest Distance 0 hops via neighbor 0: ' +
            'other hops/neighbors - 1/2'
        )
        depth_chart.append(
            'Node 4: Shortest Distance 2 hops via neighbor 6: ' +
            'other hops/neighbors - 3/7'
        )
        depth_chart.append(
            'Node 5: Shortest Distance 3 hops via neighbor 4: ' +
            'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 6: Shortest Distance 1 hops via neighbor 2: ' +
            'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 7: Shortest Distance 2 hops via neighbor 6: ' +
            'other hops/neighbors - 3/4'
        )
        depth_chart.append(
            'Node 8: Shortest Distance 3 hops via neighbor 10: ' +
            'other hops/neighbors - 4/11'
        )
        depth_chart.append(
            'Node 9: Shortest Distance 4 hops via neighbor 8: ' +
            'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 10: Shortest Distance 2 hops via neighbor 6: ' +
            'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 11: Shortest Distance 3 hops via neighbor 10: ' +
            'other hops/neighbors - 4/8'
        )
        depth_chart.append(
            'Node 12: Shortest Distance 4 hops via neighbor 14: ' +
            'other hops/neighbors - 5/15'
        )
        depth_chart.append(
            'Node 13: Shortest Distance 5 hops via neighbor 12: ' +
            'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 14: Shortest Distance 3 hops via neighbor 10: ' +
            'other hops/neighbors -'
        )
        depth_chart.append(
            'Node 15: Shortest Distance 4 hops via neighbor 14: ' +
            'other hops/neighbors - 5/12'
        )


        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")
        with open('%s/%s' % (work_dir, filename), 'w') as dc_file:
            for dchart in depth_chart:
                dc_file.write(dchart + '\n')
            dc_file.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    # pylint: disable=W0222
    def fabric_get_linkstats(self, filename, tftp_addr=None,
        link=None):
        """Upload a link_stats file from the node to TFTP"""
        self.executed.append(('fabric_get_linkstats', link))

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        link_stats = []
        link_stats.append('Packet Counts for Link %s:' % link)
        link_stats.append('Link0 StatspFS_LCn_CFG_0(link) = 0x1030d07f')
        link_stats.append('pFS_LCn_CFG_1 = 0x105f')
        link_stats.append('pFS_LCn_STATE = 0x1033')
        link_stats.append('pFS_LCn_SC_STAT = 0x0')
        link_stats.append('pFS_LCn_PKT_CNT_0 = 0x0')
        link_stats.append('pFS_LCn_PKT_CNT_1 = 0x0')
        link_stats.append('pFS_LCn_BYTE_CNT_0 = 0x0')
        link_stats.append('pFS_LCn_BYTE_CNT_1 = 0x0')
        link_stats.append('pFS_LCn_CM_TXDATA_0 = 0x82000000')
        link_stats.append('pFS_LCn_CM_TXDATA_1 = 0x0')
        link_stats.append('pFS_LCn_CM_RXDATA_0 = 0x0')
        link_stats.append('pFS_LCn_CM_RXDATA_1 = 0x0')
        link_stats.append('pFS_LCn_PKT_CNT_0 = 0x0')
        link_stats.append('pFS_LCn_PKT_CNT_1 = 0x0')
        link_stats.append('pFS_LCn_RMCSCNT = 0x1428')
        link_stats.append('pFS_LCn_RUCSCNT = 0x116')
        link_stats.append('pFS_LCn_RERRSCNT = 0x0')
        link_stats.append('pFS_LCn_RDRPSCNT = 0xb4')
        link_stats.append('pFS_LCn_RPKTSCNT = 0x0')
        link_stats.append('pFS_LCn_TPKTSCNT = 0x1')
        link_stats.append('pFS_LCn_TDRPSCNT = 0x0')

        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")
        with open('%s/%s' % (work_dir, filename), 'w') as ls_file:
            for stat in link_stats:
                ls_file.write(stat + '\n')
            ls_file.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    def fabric_config_get_ip_info(self, filename, tftp_addr=None):
        """ Upload an ipinfo file from the node to TFTP"""
        self.executed.append("fabric_config_get_ip_info")

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")

        # Create IP info file
        ipinfo = open("%s/%s" % (work_dir, filename), "w")
        for i in range(len(ADDRESSES)):
            ipinfo.write("Node %i: %s\n" % (i, ADDRESSES[i]))
        ipinfo.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    def fabric_config_get_uplink_info(self, filename, tftp_addr=None):
        self.executed.append("fabric_config_get_uplink_info")

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")
        # Create uplink info file
        ulinfo = open("%s/%s" % (work_dir, filename), "w")
        for i in range(1, NUM_NODES):
            ulinfo.write("Node %i: eth0 0, eth1 0, mgmt 0\n" % i)
        ulinfo.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    def fabric_config_get_uplink(self, iface):
        self.executed.append(("fabric_config_get_uplink", iface))
        return 0

    def fabric_config_set_uplink(self, uplink, iface):
        self.executed.append(("fabric_config_set_uplink", uplink, iface))

    def fabric_config_get_mac_addresses(self, filename, tftp_addr=None):
        """ Upload a macaddrs file from the node to TFTP"""
        self.executed.append("fabric_config_get_mac_addresses")

        if not(tftp_addr):
            raise IpmiError('No tftp address!')

        work_dir = tempfile.mkdtemp(prefix="cxmanage_test-")

        # Create macaddrs file
        macaddrs = open("%s/%s" % (work_dir, filename), "w")
        for i in range(len(ADDRESSES)):
            for port in range(3):
                macaddr = "00:00:00:00:%x:%x" % (i, port)
                macaddrs.write("Node %i, Port %i: %s\n" % (i, port, macaddr))
        macaddrs.close()

        # Upload to tftp
        address, port = tftp_addr.split(":")
        port = int(port)
        tftp = ExternalTftp(address, port)
        tftp.put_file("%s/%s" % (work_dir, filename), filename)

        shutil.rmtree(work_dir)

    def fabric_config_get_ip_src(self):
        self.executed.append('fabric_config_get_ip_src')
        return 2

    def fabric_config_set_ip_src(self, ipsrc_mode):
        self.fabric_ipsrc = ipsrc_mode
        self.executed.append('fabric_config_set_ip_src')

    def fabric_config_factory_default(self):
        self.executed.append('fabric_config_factory_default')

    def fabric_config_get_ip_addr_base(self):
        """Provide a fake base IP addr"""
        self.executed.append('fabric_config_get_ip_addr_base')
        return self.ipaddr_base

    def fabric_config_update_config(self):
        self.executed.append('fabric_config_update_config')

    def fabric_get_linkspeed(self, link="", actual=""):
        self.executed.append('fabric_get_linkspeed')
        return 1

    def fabric_config_get_linkspeed(self):
        self.executed.append('fabric_config_get_linkspeed')
        return 1

    def fabric_config_set_linkspeed(self, linkspeed):
        self.fabric_linkspeed = linkspeed
        self.executed.append('fabric_config_set_linkspeed')

    def fabric_config_get_linkspeed_policy(self):
        self.executed.append('fabric_config_get_linkspeed_policy')
        return 1

    def fabric_config_set_linkspeed_policy(self, ls_policy):
        self.fabric_ls_policy = ls_policy
        self.executed.append('fabric_config_set_linkspeed_policy')

    def fabric_config_get_link_users_factor(self):
        self.executed.append('fabric_config_get_link_users_factor')
        return 1

    def fabric_config_set_link_users_factor(self, lu_factor):
        self.fabric_lu_factor = lu_factor
        self.executed.append('fabric_config_set_link_users_factor')

    def fabric_config_set_macaddr_base(self, macaddr):
        self.executed.append(('fabric_config_set_macaddr_base', macaddr))

    def fabric_config_get_macaddr_base(self):
        self.executed.append('fabric_config_get_macaddr_base')
        return "00:00:00:00:00:00"

    def fabric_config_set_macaddr_mask(self, mask):
        self.executed.append(('fabric_config_set_macaddr_mask', mask))

    def fabric_config_get_macaddr_mask(self):
        self.executed.append('fabric_config_get_macaddr_mask')
        return "00:00:00:00:00:00"

    def fabric_add_macaddr(self, nodeid=0, iface=0, macaddr=None):
        self.executed.append('fabric_add_macaddr')

    def fabric_rm_macaddr(self, nodeid=0, iface=0, macaddr=None):
        self.executed.append('fabric_rm_macaddr')

    def fabric_get_uplink_info(self):
        """Corresponds to Node.get_uplink_info()"""
        self.executed.append('get_uplink_info')
        return 'Node 0: eth0 0, eth1 0, mgmt 0'

    def fabric_get_uplink_speed(self):
        """Corresponds to Node.get_uplink_speed()"""
        self.executed.append('get_uplink_speed')
        return 1

    def fru_read(self, fru_number, filename):
        if fru_number == 81:
            self.executed.append('node_fru_read')
        elif fru_number == 82:
            self.executed.append('slot_fru_read')
        else:
            self.executed.append('fru_read')

        with open(filename, "w") as fru_image:
            # Writes a fake FRU image with version "0.0"
            fru_image.write("x00" * 516 + "0.0" + "x00"*7673)


# pylint: disable=R0913, R0903
class Partition(object):
    """Partition class."""
    def __init__(self, partition, type_, offset=0,
            size=0, priority=0, daddr=0, in_use=None):
        self.updates = 0
        self.retrieves = 0
        self.checks = 0
        self.activates = 0
        self.fwinfo = FWInfoEntry(partition, type_, offset, size, priority,
                                  daddr, in_use)


class FWInfoEntry(object):
    """ Firmware info for a single partition """

    def __init__(self, partition, type_, offset=0, size=0, priority=0, daddr=0,
                  in_use=None):
        self.partition = "%2i" % partition
        self.type = {
                2: "02 (S2_ELF)",
                3: "03 (SOC_ELF)",
                10: "0a (CDB)",
                11: "0b (UBOOTENV)"
            }[type_]
        self.offset = "%8x" % offset
        self.size = "%8x" % size
        self.priority = "%8x" % priority
        self.daddr = "%8x" % daddr
        self.in_use = {None: "Unknown", True: "1", False: "0"}[in_use]
        self.flags = "fffffffd"
        self.version = "v0.0.0"


class DummyUbootEnv(UbootEnv):
    """UbootEnv info."""

    def get_boot_order(self):
        """Hard coded boot order for testing."""
        return ["disk", "pxe"]

    def set_boot_order(self, boot_args):
        """ Do nothing """
        pass

# pylint: disable=R0903
class DummyIPRetriever(object):
    """ Dummy IP retriever """

    def __init__(self, ecme_ip, aggressive=False, verbosity=0, **kwargs):
        self.executed = False
        self.ecme_ip = ecme_ip
        self.aggressive = aggressive
        self.verbosity = verbosity
        for name, value in kwargs.iteritems():
            setattr(self, name, value)

    def run(self):
        """ Set the server_ip variable. Raises an error if called more than
        once. """
        if self.executed:
            raise IPDiscoveryError("DummyIPRetriever.run() was called twice!")
        self.executed = True
        self.server_ip = "192.168.200.1"

# End of file: node_test.py
