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
import sys
import atexit
import shutil
import socket
import logging
import traceback

from tftpy import TftpClient, TftpServer, setLogLevel
from threading import Thread
from cxmanage_api import temp_dir
from tftpy.TftpShared import TftpException


class InternalTftp(object):
    """Internally serves files using the `Trivial File Transfer Protocol <http://en.wikipedia.org/wiki/Trivial_File_Transfer_Protocol>`_.

    >>> # Typical instantiation ...
    >>> from cxmanage_api.tftp import InternalTftp
    >>> i_tftp = InternalTftp()
    >>> # Alternatively, you can specify an address or hostname ...
    >>> i_tftp = InternalTftp(ip_address='localhost')

    :param ip_address: Ip address for the Internal TFTP server to use.
    :type ip_address: string
    :param port: Port for the internal TFTP server.
    :type port: integer
    :param verbose: Flag to turn on additional messaging.
    :type verbose: boolean

    """

    def __init__(self, ip_address=None, port=0, verbose=True):
        """Default constructor for the InternalTftp class."""
        self.tftp_dir = temp_dir()
        self.verbose = verbose
        pipe = os.pipe()
        pid = os.fork()
        if (not pid):
            # Create a PortThread class only if needed ...
            class PortThread(Thread):
                """Thread that sends the port number through the pipe."""
                def run(self):
                    """Run function override."""
                    # Need to wait for the server to open its socket
                    while not server.sock:
                        pass
                    with os.fdopen(pipe[1], "w") as a_file:
                        a_file.write("%i\n" % server.sock.getsockname()[1])
            #
            # Create an Internal TFTP server thread
            #
            server = TftpServer(tftproot=self.tftp_dir)
            thread = PortThread()
            thread.start()
            try:
                if (self.verbose):
                    setLogLevel(logging.CRITICAL)
                # Start accepting connections ...
                server.listen(ip_address, port)
            except KeyboardInterrupt:
                # User @ keyboard cancelled server ...
                if (self.verbose):
                    traceback.format_exc()
            sys.exit(0)

        self.server = pid
        self.ip_address = ip_address
        with os.fdopen(pipe[0]) as a_fd:
            self.port = int(a_fd.readline())
        atexit.register(self.kill)

    def get_port(self):
        """Returns the listening port of this server.

        >>> i_tftp.get_port()
        40865

        :return: The listening port of this Internal TFTP server.
        :rtype: integer

        """
        return self.port

    def get_address(self, relative_host=None):
        """Returns the ipv4 address of this server.
        If a relative_host is specified, then we discover our address to them.

        >>> i_tftp.get_address(relative_host='10.10.14.150')
        'localhost'

        :param relative_host: Ip address to the relative host.
        :type relative_host: string

        :return: The ipv4 address of this InternalTftpServer.
        :rtype: string

        """
        if ((self.ip_address != None) or (relative_host == None)):
            return self.ip_address
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((relative_host, self.port))
            ipv4 = sock.getsockname()[0]
            sock.close()
            return ipv4

    def kill(self):
        """Kills the InternalTftpServer.

        >>> i_tftp.kill()

        """
        if (self.server):
            os.kill(self.server, 15)
            self.server = None

    def get_file(self, src, dest):
        """Download a file from the tftp server to local_path.

        >>> i_tftp.get_file(src='remote_file_i_want.txt', dest='/local/path')

        :param src: Source file path on the tftp_server.
        :type src: string
        :param dest: Destination path (on your machine) to copy the TFTP file to.
        :type dest: string

        """
        src = "%s/%s" % (self.tftp_dir, src)
        if (src != dest):
            try:
                # Ensure the file exists ...
                with open(src) as a_file:
                    a_file.close()
                shutil.copy(src, dest)

            except Exception:
                traceback.format_exc()
                raise

    def put_file(self, src, dest):
        """Upload a file from src to dest on the tftp server (path).

        >>> i_tftp.put_file(src='/local/file.txt', dest='remote_file_name.txt')

        :param src: Path to the local file to send to the TFTP server.
        :type src: string
        :param dest: Path to put the file to on the TFTP Server.
        :type dest: string

        """
        dest = "%s/%s" % (self.tftp_dir, dest)
        if (src != dest):
            try:
                # Ensure that the local file exists ...
                with open(src) as a_file:
                    a_file.close()
                shutil.copy(src, dest)
            except Exception:
                traceback.format_exc()
                raise


class ExternalTftp(object):
    """Defines a ExternalTftp object, which is actually TFTP client.

    >>> from cxmanage_api.tftp import ExternalTftp
    >>> e_tftp = ExternalTftp(ip_address='1.2.3.4')

    :param ip_address: Ip address of the TFTP server.
    :type ip_address: string
    :param port: Port to the External TFTP server.
    :type port: integer
    :param verbose: Flag to turn on verbose output (cmd/response).
    :type verbose: boolean

    """

    def __init__(self, ip_address, port=69, verbose=True):
        """Default constructor for this the ExternalTftp class."""
        self.ip_address = ip_address
        self.port = port
        self.verbose = verbose

        if (self.verbose):
            setLogLevel(logging.CRITICAL)

    def get_address(self, relative_host=None):
        """Return the ip address of the ExternalTftp server.

        >>> e_tftp.get_address()
        '1.2.3.4'

        :param relative_host: Unused parameter present only for function signature.
        :type relative_host: None

        :returns: The ip address of the external TFTP server.
        :rtype: string

        """
        del relative_host  # Needed only for function signature.
        return self.ip_address

    def get_port(self):
        """Return the listening port of this server.

        >>> e_tftp.get_port()
        69

        :returns: The port of the external TFTP server connection.
        :rtype: integer

        """
        return self.port

    def get_file(self, src, dest):
        """Download a file from the ExternalTftp Server.

        .. note::
            * TftpClient is not threadsafe, so we create a unique instance for
              each transfer.

        >>> e_tftp.get_file(src='remote_file_i_want.txt', dest='/local/path')

        :param src: The path to the file on the Tftp server.
        :type src: string
        :param dest: The local destination to copy the file to.
        :type dest: string

        :raises TftpException: If the file does not exist or cannot be obtained
                               from the TFTP server.
        :raises TftpException: If a TypeError is received from tftpy.

        """
        try:
            client = TftpClient(self.ip_address, self.port)
            client.download(output=dest, filename=src)
        except TftpException:
            if (self.verbose):
                traceback.format_exc()
            raise
        except TypeError:
            if (self.verbose):
                traceback.format_exc()
            raise TftpException("Failed download file from TFTP server")

    def put_file(self, src, dest):
        """Uploads a file to the tftp server.

        .. note::
            * TftpClient is not threadsafe, so we create a unique instance for
              each transfer.

        >>> e_tftp.put_file(src='local_file.txt', dest='remote_name.txt')

        :param src: Source file path (on your local machine).
        :type src: string
        :param dest: Destination path (on the TFTP server).
        :type dest: string

        :raises TftpException: If the file cannot be written to the TFTP server.
        :raises TftpException: If a TypeError is received from tftpy.

        """
        try:
            client = TftpClient(self.ip_address, self.port)
            client.upload(input=src, filename=dest)
        except TftpException:
            if (self.verbose):
                traceback.format_exc()
            raise
        except TypeError:
            if (self.verbose):
                traceback.format_exc()
            raise TftpException("Failed to upload file to TFTP server")


# End of file: ./tftp.py
