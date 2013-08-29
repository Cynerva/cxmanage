"""Calxeda: cx_exceptions.py"""


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
# We expose these here so a user does not have to import from pyipmi or tftpy.
#
# pylint: disable=W0611
#
from pyipmi import IpmiError

from tftpy.TftpShared import TftpException


#
# Defines the custom exceptions used by the cxmanage_api project.
#


class TimeoutError(Exception):
    """Raised when a timeout has been reached.

    >>> from cxmanage_api.cx_exceptions import TimeoutError
    >>> raise TimeoutError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.TimeoutError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When a timeout has been reached.

    """

    def __init__(self, msg):
        """Default constructor for the TimoutError class."""
        super(TimeoutError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class NoPartitionError(Exception):
    """Raised when a partition is not found.

    >>> from cxmanage_api.cx_exceptions import NoPartitionError
    >>> raise NoPartitionError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.NoPartitionError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When a partition is not found.

    """

    def __init__(self, msg):
        """Default constructor for the NoPartitionError class."""
        super(NoPartitionError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class NoSensorError(Exception):
    """Raised when a sensor or sensors are not found.

    >>> from cxmanage_api.cx_exceptions import NoSensorError
    >>> raise NoSensorError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.NoSensorError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When a sensor or sensors are not found.

    """

    def __init__(self, msg):
        """Default constructor for the NoSensorError class."""
        super(NoSensorError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class SocmanVersionError(Exception):
    """Raised when there is an error with the users socman version.

    >>> from cxmanage_api.cx_exceptions import SocmanVersionError
    >>> raise SocmanVersionError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.SocmanVersionError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When there is an error with the users socman version.

    """

    def __init__(self, msg):
        """Default constructor for the SocmanVersionError class."""
        super(SocmanVersionError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class FirmwareConfigError(Exception):
    """Raised when there are slot/firmware version inconsistencies.

    >>> from cxmanage_api.cx_exceptions import FirmwareConfigError
    >>> raise FirmwareConfigError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.FirmwareConfigError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When there are slot/firmware version inconsistencies.

    """

    def __init__(self, msg):
        """Default constructor for the FirmwareConfigError class."""
        super(FirmwareConfigError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class PriorityIncrementError(Exception):
    """Raised when the Priority on a SIMG image cannot be altered.

    >>> from cxmanage_api.cx_exceptions import PriorityIncrementError
    >>> raise PriorityIncrementError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.PriorityIncrementError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When the Priority on a SIMG image cannot be altered.

    """

    def __init__(self, msg):
        """Default constructor for the PriorityIncrementError class."""
        super(PriorityIncrementError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class ImageSizeError(Exception):
    """Raised when the actual size of the image is not what is expected.

    >>> from cxmanage_api.cx_exceptions import ImageSizeError
    >>> raise ImageSizeError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.ImageSizeError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When the actual size of the image is not what is expected.

    """

    def __init__(self, msg):
        """Default constructor for the ImageSizeError class."""
        super(ImageSizeError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class TransferFailure(Exception):
    """Raised when the transfer of a file has failed.

    >>> from cxmanage_api.cx_exceptions import TransferFailure
    >>> raise TransferFailure('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.TransferFailure: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When the transfer of a file has failed.

    """

    def __init__(self, msg):
        """Default constructor for the TransferFailure class."""
        super(TransferFailure, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class InvalidImageError(Exception):
    """Raised when an image is not valid. (i.e. fails verification).

    >>> from cxmanage_api.cx_exceptions import InvalidImageError
    >>> raise InvalidImageError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.InvalidImageError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When an image is not valid. (i.e. fails verification).

    """

    def __init__(self, msg):
        """Default constructor for the InvalidImageError class."""
        super(InvalidImageError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class UbootenvError(Exception):
    """Raised when the UbootEnv class fails to interpret the ubootenv
    environment variables.

    >>> from cxmanage_api.cx_exceptions import UbootenvError
    >>> raise UbootenvError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.UbootenvError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When ubootenv settings are unrecognizable.

    """

    def __init__(self, msg):
        """Default constructor for the UbootenvError class."""
        super(UbootenvError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class CommandFailedError(Exception):
    """Raised when a command has failed.

    >>> from cxmanage_api.cx_exceptions import CommandFailedError
    >>> raise CommandFailedError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.CommandFailedError: My custom exception text!

    :param results: Command results. (map of nodes->results)
    :type results: dictionary
    :param errors: Command errors. (map of nodes->errors)
    :type errors: dictionary
    :raised: When a command has failed.

    """

    def __init__(self, results, errors):
        """Default constructor for the CommandFailedError class."""
        super(CommandFailedError, self).__init__()
        self.results = results
        self.errors = errors

    def __repr__(self):
        return 'Results: %s Errors: %s' % (self.results, self.errors)

    def __str__(self):
        return str(dict((x, str(y)) for x, y in self.errors.iteritems()))


class PartitionInUseError(Exception):
    """Raised when trying to upload to a CDB/BOOT_LOG partition that's in use.

    >>> from cxmanage_api.cx_exceptions import PartitionInUseError
    >>> raise PartitionInUseError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.PartitionInUseError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When trying to upload to a CDB/BOOT_LOG partition that's in use.

    """

    def __init__(self, msg):
        """Default constructor for the PartitionInUseError class."""
        super(PartitionInUseError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg


class IPDiscoveryError(Exception):
    """Raised when server IP discovery fails for any reason.

    >>> from cxmanage_api.cx_exceptions import IPDiscoveryError
    >>> raise IPDiscoveryError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.IPDiscoveryError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When IP discovery fails for any reason.

    """

    def __init__(self, msg):
        """Default constructor for the IPDsicoveryError class."""
        super(IPDiscoveryError, self).__init__()
        self.msg = msg

    def __str__(self):
        """String representation of this Exception class."""
        return self.msg

class NoFRUVersionError(Exception):
    """Raised when a node does not detect a FRU version.

    >>> from cxmanage_api.cx_exceptions import NoFRUError
    >>> raise NoFRUError('My custom exception text!')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    cxmanage_api.cx_exceptions.NoFRUError: My custom exception text!

    :param msg: Exceptions message and details to return to the user.
    :type msg: string
    :raised: When a node fails to detect a FRU version

    """

    def __init__(self, msg="No FRU version detected"):
        super(NoFRUVersionError, self).__init__()
        self.msg = msg
    def __str__(self):
        return self.msg

# End of file: exceptions.py
