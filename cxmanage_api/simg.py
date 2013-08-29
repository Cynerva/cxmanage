"""Calxeda: simg.py"""


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

from cxmanage_api.crc32 import get_crc32


HEADER_LENGTH = 60
MIN_HEADER_LENGTH = 28


# pylint: disable=R0913, R0903, R0902
class SIMGHeader(object):
    """Container for an SIMG header.

    >>> from cxmanage_api.simg import SIMGHeader
    >>> simg = SIMGHeader()

    :param header_string: SIMG Header value.
    :type header_string: string

    """

    def __init__(self, header_string=None):
        """Default constructor for the SIMGHeader class."""
        if (header_string == None):
            self.magic_string = 'SIMG'
            self.hdrfmt = 2
            self.priority = 0
            self.imgoff = HEADER_LENGTH
            self.imglen = 0
            self.daddr = 0
            self.flags = 0
            self.crc32 = 0
            self.version = ''
        else:
            header_string = header_string.ljust(HEADER_LENGTH, chr(0))
            tup = struct.unpack('<4sHHIIIII32s', header_string)
            self.magic_string = tup[0]
            self.hdrfmt = tup[1]
            self.priority = tup[2]
            self.imgoff = tup[3]
            self.imglen = tup[4]
            self.daddr = tup[5]
            self.flags = tup[6]
            self.crc32 = tup[7]
            if (self.hdrfmt >= 2):
                self.version = tup[8]
            else:
                self.version = ''

    def __str__(self):
        return struct.pack('<4sHHIIIII32s', self.magic_string, self.hdrfmt,
                           self.priority, self.imgoff, self.imglen, self.daddr,
                           self.flags, self.crc32, self.version)

def create_simg(contents, priority=0, daddr=0, skip_crc32=False, align=False,
                  version=None):
    """Create an SIMG version of a file.

    >>> from cxmanage_api.simg import create_simg
    >>> simg = create_simg(contents='foobarbaz')
    >>> simg
    'SIMG\\x02\\x00\\x00\\x00<\\x00\\x00\\x00\\t\\x00\\x00\\x00\\x00\\x00\\x00
    \\x00\\xff\\xff\\xff\\xffK\\xf3\\xea\\x0c\\x00\\x00\\x00\\x00\\x00\\x00
    \\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00
    \\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00foobarbaz'

    :param contents: Contents of the SIMG file.
    :type contents: string
    :param priority: SIMG Header priority value.
    :type priority: integer
    :param daddr: SIMG Header daddr value.
    :type daddr: integer
    :param skip_crc32: Flag to skip crc32 calculating.
    :type skip_crc32: boolean
    :param align: Flag used to turn on/off image offset of 4096.
    :type align: boolean
    :param version: Version string.
    :type version: string

    :returns: String representation of the SIMG file.
    :rtype: string

    """
    if (version == None):
        version = ''

    header = SIMGHeader()
    header.priority = priority
    header.imglen = len(contents)
    header.daddr = daddr
    header.version = version

    if (align):
        header.imgoff = 4096
    # Calculate crc value
    if (skip_crc32):
        crc32 = 0
    else:
        crc32 = get_crc32(contents, get_crc32(str(header)[:MIN_HEADER_LENGTH]))
    # Get SIMG header
    header.flags = 0xFFFFFFFF
    header.crc32 = crc32
    return str(header).ljust(header.imgoff, chr(0)) + contents

def has_simg(simg):
    """Returns true if this string has an SIMG header.

    >>> from cxmanage_api.simg import create_simg
    >>> simg=create_simg(contents='foobarbaz')
    >>> from cxmanage_api.simg import has_simg
    >>> has_simg(simg=simg)
    True

    :param simg: SIMG string (representation of a SIMG file).
    :type simg: string

    :returns: Whether or not the string has a SIMG header.
    :rtype: boolean

    """
    if (len(simg) < MIN_HEADER_LENGTH):
        return False
    header = SIMGHeader(simg[:HEADER_LENGTH])
    # Check for magic word
    return (header.magic_string == 'SIMG')

def valid_simg(simg):
    """Return true if this is a valid SIMG.

    >>> from cxmanage_api.simg import create_simg
    >>> simg=create_simg(contents='foobarbaz')
    >>> from cxmanage_api.simg import valid_simg
    >>> valid_simg(simg=simg)
    True

    :param simg: SIMG string (representation of a SIMG file).
    :type simg: string

    :returns: Whether or not the SIMG is valid.
    :rtype: boolean

    """
    if (not has_simg(simg)):
        return False
    header = SIMGHeader(simg[:HEADER_LENGTH])

    # Check offset
    if (header.imgoff < MIN_HEADER_LENGTH):
        return False

    # Check length
    start = header.imgoff
    end = start + header.imglen
    contents = simg[start:end]
    if (len(contents) < header.imglen):
        return False

    # Check crc32
    crc32 = header.crc32
    if (crc32 != 0):
        header.flags = 0
        header.crc32 = 0
        if (crc32 != get_crc32(contents,
                               get_crc32(str(header)[:MIN_HEADER_LENGTH]))):
            return False
    return True

def get_simg_header(simg):
    """Returns the header of this SIMG.

    >>> from cxmanage_api.simg import get_simg_header
    >>> get_simg_header(x)
    <cxmanage_api.simg.SIMGHeader instance at 0x7f4d1ce9aef0>

    :param simg: Path to SIMG file.
    :type simg: string

    :returns: The SIMG header.
    :rtype: string

    :raises ValueError: If the SIMG cannot be read.

    """
    if (not valid_simg(simg)):
        raise ValueError("Failed to read invalid SIMG")
    return SIMGHeader(simg[:HEADER_LENGTH])

def get_simg_contents(simg):
    """Returns the contents of this SIMG.

    >>> from cxmanage_api.simg import get_simg_contents
    >>> get_simg_contents(simg=simg)
    'foobarbaz'

    :param simg: Path to SIMG file.
    :type simg: string

    :returns: Contents of this SIMG.
    :rtype: string

    """
    header = get_simg_header(simg)
    start = header.imgoff
    end = start + header.imglen
    return simg[start:end]


# End of file: ./simg.py

