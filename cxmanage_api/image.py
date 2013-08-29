"""Calxeda: image.py"""


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
import subprocess

from cxmanage_api import temp_file
from cxmanage_api.simg import create_simg, has_simg
from cxmanage_api.simg import valid_simg, get_simg_contents
from cxmanage_api.cx_exceptions import InvalidImageError


class Image(object):
    """An Image consists of: an image type, a filename, and SIMG header info.

    >>> from cxmanage_api.image import Image
    >>> img = Image(filename='spi_highbank.bin', image_type='PACAKGE')

    :param filename: Path to the image.
    :type filename: string
    :param image_type: Type of image. [CDB, BOOT_LOG, SOC_ELF]
    :type image_type: string
    :param simg: Path to the simg file.
    :type simg: string
    :param daddr: The daddr field in the SIMG Header.
    :type daddr: integer
    :param skip_crc32: Flag to skip (or not) CRC32 checking.
    :type skip_crc32: boolean
    :param version: Image version.
    :type version: string

    :raises ValueError: If the image file does not exist.
    :raises InvalidImageError: If the file is NOT a valid image.

    """

    # pylint: disable=R0913
    def __init__(self, filename, image_type, simg=None, daddr=None,
                  skip_crc32=False, version=None):
        """Default constructor for the Image class."""
        self.filename = filename
        self.type = image_type
        self.daddr = daddr
        self.skip_crc32 = skip_crc32
        self.version = version

        if (not os.path.exists(filename)):
            raise ValueError("File %s does not exist" % filename)

        if (simg == None):
            contents = open(filename, "rb").read()
            self.simg = has_simg(contents)
        else:
            self.simg = simg

        if (not self.verify()):
            raise InvalidImageError("%s is not a valid %s image" %
                                    (filename, image_type))

    def render_to_simg(self, priority, daddr):
        """Creates a SIMG file.

        >>> img.render_to_simg(priority=1, daddr=0)
        >>> 'spi_highbank.bin'

        :param priority: SIMG header priority value.
        :type priority: integer
        :param daddr: SIMG daddr field value.
        :type daddr: integer

        :returns: The file name of the image.
        :rtype: string

        :raises InvalidImageError: If the SIMG image is not valid.

        """
        filename = self.filename
        # Create new image if necessary
        if (not self.simg):
            contents = open(filename, "rb").read()
            # Figure out daddr
            if (self.daddr != None):
                daddr = self.daddr
            # Create simg
            align = (self.type in ["CDB", "BOOT_LOG"])
            simg = create_simg(contents, priority=priority, daddr=daddr,
                    skip_crc32=self.skip_crc32, align=align,
                    version=self.version)
            filename = temp_file()
            with open(filename, "wb") as file_:
                file_.write(simg)

        # Make sure the simg was built correctly
        if (not valid_simg(open(filename, "rb").read())):
            raise InvalidImageError("%s is not a valid SIMG" %
                    os.path.basename(self.filename))

        return filename

    def size(self):
        """Return the full size of this image (as an SIMG)

        >>> img.size()
        2174976

        :returns: The size of the image file in bytes.
        :rtype: integer

        """
        if (self.simg):
            return os.path.getsize(self.filename)
        else:
            contents = open(self.filename, "rb").read()
            align = (self.type in ["CDB", "BOOT_LOG"])
            simg = create_simg(contents, skip_crc32=True, align=align)
            return len(simg)

    def verify(self):
        """Returns true if the image is valid, false otherwise.

        >>> img.verify()
        True

        :returns: Whether or not the image file is valid.
        :rtype: boolean

        """
        if (self.type == "SOC_ELF" and not self.simg):
            try:
                file_process = subprocess.Popen(["file", self.filename],
                                                stdout=subprocess.PIPE)
                file_type = file_process.communicate()[0].split()[1]

                if (file_type != "ELF"):
                    return False
            except OSError:
                # "file" tool wasn't found, just continue without it
                # typically located: /usr/bin/file
                pass

        if (self.type in ["CDB", "BOOT_LOG"]):
            # Look for "CDBH"
            contents = open(self.filename, "rb").read()
            if (self.simg):
                contents = get_simg_contents(contents)
            if (contents[:4] != "CDBH"):
                return False
        return True


# End of file: ./image.py
