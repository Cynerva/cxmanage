"""Calxeda: ip_retriever.py"""


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
import re
import json

import threading
from time import sleep

from cxmanage_api.cx_exceptions import IPDiscoveryError

if sys.platform != 'win32':
    from pexpect import TIMEOUT, EOF
from pyipmi import make_bmc
from pyipmi.server import Server
from pyipmi.bmc import LanBMC


# pylint: disable=R0902
class IPRetriever(threading.Thread):
    """The IPRetriever class takes an ECME address and when run will
       connect to the Linux Server from the ECME over SOL and use
       ifconfig to determine the IP address.
    """
    verbosity = None
    aggressive = None
    retry = None
    timeout = None
    interface = None

    ecme_ip = None
    ecme_user = None
    ecme_password = None

    server_ip = None
    server_user = None
    server_password = None

    def __init__(self, ecme_ip, aggressive=False, verbosity=0, **kwargs):
        """Initializes the IPRetriever class. The IPRetriever needs the
           only the first node to know where to start.
        """
        super(IPRetriever, self).__init__()
        self.daemon = True

        if hasattr(ecme_ip, 'ip_address'):
            self.ecme_ip = ecme_ip.ip_address
        else:
            self.ecme_ip = ecme_ip

        self.aggressive = aggressive
        self.verbosity = verbosity

        # Everything here is optional
        self.timeout = kwargs.get('timeout', 120)
        self.retry = kwargs.get('retry', 0)

        self.ecme_user = kwargs.get('ecme_user', 'admin')
        self.ecme_password = kwargs.get('ecme_password', 'admin')

        self.server_user = kwargs.get('server_user', 'user1')
        self.server_password = kwargs.get('server_password', '1Password')

        if '_inet_pattern' in kwargs and '_ip_pattern' in kwargs:
            self.interface = kwargs.get('interface', None)
            self._inet_pattern = kwargs['_inet_pattern']
            self._ip_pattern = kwargs['_ip_pattern']

        else:
            self.set_interface(kwargs.get('interface', None),
                               kwargs.get('ipv6', False))

        if 'bmc' in kwargs:
            self._bmc = kwargs['bmc']
        else:
            self._bmc = make_bmc(LanBMC, verbose=(self.verbosity > 1),
                                 hostname=self.ecme_ip,
                                 username=self.ecme_user,
                                 password=self.ecme_password)

        if 'config_path' in kwargs:
            self.read_config(kwargs['config_path'])



    def set_interface(self, interface=None, ipv6=False):
        """Sets the interface and IP Version that is looked for on the server.
           The interface must be acceptable by ifconfig. By default the first
           interface given by ifconfig will be used.
        """
        self.interface = interface

        if not ipv6:
            self._ip_pattern = re.compile(r'\d+\.' * 3 + r'\d+')
            self._inet_pattern = re.compile('inet addr:(%s)' %
                                            self._ip_pattern.pattern)
        else:
            self._ip_pattern = re.compile(
                '[0-9a-fA-F:]*:' * 2 + '[0-9a-fA-F:]+'
            )
            self._inet_pattern = re.compile('inet6 addr: ?(%s)' %
                                            self._ip_pattern.pattern)


    def _log(self, msg, error=False):
        """Print message with the ECME IP if verbosity is normal."""
        if error:
            sys.stderr.write('Error %s: %s\n' % (self.ecme_ip, msg))
        elif self.verbosity > 0:
            sys.stdout.write('%s: %s\n' % (self.ecme_ip, msg))


    def run(self):
        """Attempts to finds the server IP address associated with the
           ECME IP. If successful, server_ip will contain the IP address.
        """
        if self.server_ip is not None:
            self._log('Using stored IP %s' % self.server_ip)
            return

        for _ in range(self.retry + 1):
            self.server_ip = self.sol_try_command(self.sol_find_ip)

            if self.server_ip is not None:
                self._log('The server IP is %s' % self.server_ip)
                return

        self._log('The server IP could not be found')


    def _power_server(self, cycle=False):
        """Puts the server in a powered state with conditions that should
           result in a successful SOL activation. Returns True if successful.
        """
        server = Server(self._bmc)

        if cycle:
            self._log('Powering server off')
            server.power_off()
            sleep(5)

        if not server.is_powered:
            self._log('Powering server on')
            server.power_on()
            sleep(10)

        return server.is_powered


    def sol_find_ip(self, session):
        """Uses ifconfig to get the IP address in an SOL session.
           Returns the ip address if it is found or None on failure.
        """
        if self.interface:
            session.sendline('ifconfig %s' % self.interface)
        else:
            session.sendline('ifconfig')

        index = session.expect(['Link encap', 'error fetching interface',
                               TIMEOUT, EOF], timeout=2)

        # ifconfig found the interface
        if index == 0:
            output = ''.join(session.readline() for line in range(3))
            found_ip = self._inet_pattern.findall(output)

            if found_ip:
                return found_ip[0]
            else:
                self._bmc.deactivate_payload()
                raise IPDiscoveryError('Interface %s does not have '
                                   'given address' % self.interface)
        elif index == 1:
            self._bmc.deactivate_payload()
            raise IPDiscoveryError('Could not find interface %s'
                    % self.interface)

        else:  # Failed to find interface. Returning None
            return None


    # pylint: disable=R0912, R0915
    def sol_try_command(self, command):
        """Connects to the server over a SOL connection. Attempts
           to run the given command on the server without knowing
           the state of the server. The command must return None if
           it fails. If aggresive is True, then the server may be
           restarted or power cycled to try and reset the state.
        """
        server = Server(self._bmc)
        if not server.is_powered:
            self._log("Server is powered off. Can't proceed.")
            raise IPDiscoveryError("Server is powered off. Can't proceed.")

        self._log('Activating SOL')
        session = self._bmc.activate_payload()
        sleep(2)

        timeout = self.timeout
        attempt = 0
        login_attempted = False

        options = [TIMEOUT, EOF,
                   'Highbank #', 'Invalid boot device',
                   '[lL]ogin:', '[pP]assword:',
                   'network configuration',
                   'going down for reboot', 'Stopped',
                   'SOL payload already active',
                   'SOL Session operational']

        while attempt < 7:
            index = session.expect(options, timeout)

            # Catchable errors

            # May need to boot
            if index == 2:
                session.sendline('run bootcmd_sata')
                timeout = self.timeout

            # An invalid boot device can occur if bootcmd_sata fails
            elif index == 3:
                self._bmc.deactivate_payload()
                raise IPDiscoveryError('Unable to boot linux due to '
                                   'an invalid boot device')

            # Enter username or report incorrect login
            elif index == 4:
                if not login_attempted:
                    self._log('Logging into Linux')
                    session.sendline(self.server_user)

                    # now check for failed login
                    options[index] = 'incorrect'
                    login_attempted = True
                    timeout = 4
                else:
                    self._bmc.deactivate_payload()
                    raise IPDiscoveryError('Incorrect username or password')

            # Enter password
            elif index == 5:
                session.sendline(self.server_password)
                timeout = 4

            # Warn about the network configuration
            elif index == 6:
                self._log('Waiting for network configuration')
                timeout = self.timeout

            # Inform of reboot
            elif index == 7:
                self._log('Linux is rebooting')
                timeout = self.timeout

            # Inform of zombied processes
            elif index == 8:
                self._log('Suspended the current process')
                timeout = 2

            # Try restarting SOL connection
            elif index == 9:
                self._log('Restarting SOL session')
                self._bmc.deactivate_payload()
                sleep(2)
                session = self._bmc.activate_payload()
                sleep(2)
                session.sendline()
                timeout = 8

            # Successful SOL connection
            elif index == 10:
                self._log('SOL Activated')
                session.sendline()
                session.sendcontrol('z')
                timeout = 2

            else:
                # Assume where are at a prompt and able to run the command
                value = command(session)

                if value is not None:
                    self._bmc.deactivate_payload()
                    return value

                # Non catchable errors

                # Try to zombie the current process
                if attempt == 0:
                    session.sendcontrol('z')
                    timeout = 2

                elif not self.aggressive:
                    sleep(2)
                    self._bmc.deactivate_payload()
                    raise IPDiscoveryError('Unable to obtain the server\'s '
                                           'IP address unintrusively')

                # Try sending kill signals
                elif attempt == 1:
                    self._log('Sending interrupt signals')
                    session.sendcontrol('c')
                    timeout = 2


                elif attempt == 2:
                    session.sendcontrol('\\')
                    timeout = 2

                # Try exiting. Will put us in login if we were another user
                elif attempt == 3:
                    session.sendline('exit')
                    timeout = 4

                # Attempt to reboot the Linux server
                elif attempt == 4:
                    self._log('Attempting reboot')
                    session.sendline('sudo reboot')
                    sleep(1)
                    timeout = 4
                    login_attempted = False

                # If all else fails: power cycle the server
                elif attempt == 5:
                    self._power_server(cycle=True)
                    timeout = self.timeout
                    login_attempted = False

                attempt += 1

        # Reaches here if nothing succeeds
        self._bmc.deactivate_payload()
        raise IPDiscoveryError('Unable to properly connect over SOL')


    def read_config(self, path):
        """Loads the address information from a json configuration
           file written by write_config
        """
        with open(path, 'r') as json_file:
            json_data = json_file.read()
            config_data = json.loads(json_data)

            self.ecme_ip = config_data['ecme_host']
            self.server_ip = config_data['server_host']

    def write_config(self, path):
        """Saves the address information in a json configuration file"""
        config_data = {'ecme_host': self.ecme_ip,
                       'server_host': self.server_ip}

        json_data = json.dumps(config_data, indent=4)
        with open(path, 'w') as json_file:
            json_file.write(json_data)



