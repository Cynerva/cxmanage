"""Calxeda: tftp_test.py"""


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


#
# Unit tests for the Internal and External Tftp classes.
#


import os
import socket
import unittest

from cxmanage_test import random_file
from cxmanage_api.tftp import InternalTftp, ExternalTftp


def _get_relative_host():
    """Returns the test machine ip as a relative host to pass to the
    InternalTftp server.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # RFC863 defines port 9 as the UDP discard port, so we use it to
        # find out our local ip to pass as a relative_host
        return sock.getsockname()[0]

    except socket.error:
        raise

# pylint: disable=R0904
class InternalTftpTest(unittest.TestCase):
    """ Tests the functions of the InternalTftp class."""

    def setUp(self):
        """Create local Internal TFTP objects to test with."""
        self.tftp1 = InternalTftp()
        self.tftp2 = InternalTftp(ip_address='127.0.0.254')

    def test_put_and_get(self):
        """ Test file transfers on an internal host """

        # Create file
        filename = random_file(1024)
        contents = open(filename).read()

        # Upload and remove
        basename = os.path.basename(filename)
        self.tftp1.put_file(filename, basename)
        os.remove(filename)
        self.assertFalse(os.path.exists(filename))

        # Download
        self.tftp1.get_file(basename, filename)

        # Verify match
        self.assertEqual(open(filename).read(), contents)
        os.remove(filename)

    def test_get_address_with_relhost(self):
        """Tests the get_address(relative_host) function with a relative_host
        specified.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # RFC863 defines port 9 as the UDP discard port, so we use it to
            # find out our local ip to pass as a relative_host
            sock.connect((socket.gethostname(), 9))
            relative_host = sock.getsockname()[0]

        except socket.error:
            raise
        self.assertEqual(self.tftp2.ip_address,
                         self.tftp2.get_address(relative_host=relative_host))
        sock.close()


# pylint: disable=R0904
class ExternalTftpTest(unittest.TestCase):
    """Tests the ExternalTftp class.
    ..note:
        * For testing purposes the 'external' server points to an internally
          hosted one, but it allows us to make sure the actual TFTP protocol is
          working.
    """

    def setUp(self):
        """Create an ExternalTftp object to test with."""
        self.itftp = InternalTftp(ip_address='127.0.0.250')
        self.etftp = ExternalTftp(
                     self.itftp.get_address(relative_host=_get_relative_host()),
                     self.itftp.port)

    def test_put_and_get(self):
        """Test the put_file(src, dest) function. Test the get_file(src,dest)
        function by movign local files around using the TFT Protocol.
        """
        # Create file
        filename = random_file(1024)
        contents = open(filename).read()
        # Upload and remove original file
        basename = os.path.basename(filename)
        self.etftp.put_file(src=filename, dest=basename)
        os.remove(filename)
        self.assertFalse(os.path.exists(filename))
        # Download
        self.etftp.get_file(src=basename, dest=filename)
        # Verify match
        self.assertEqual(open(filename).read(), contents)
        os.remove(filename)

# End of file: ./tftp_test.py
