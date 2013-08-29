"""Calxeda: firmware_package.py"""


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
import tarfile
import ConfigParser
import pkg_resources

from cxmanage_api import temp_dir
from cxmanage_api.image import Image


# pylint: disable=R0903
class FirmwarePackage(object):
    """A firmware update package contains multiple images & version information.

    .. note::
        * Valid firmware packages are in tar.gz format.

    >>> from cxmanage_api.firmware_package import FirmwarePackage
    >>> fwpkg = FirmwarePackage('/path/to/ECX-1000_update-v1.7.1-dirty.tar.gz')

    :param filename: The file to extract and read.
    :type filename: string

    :raises ValueError: If cxmanage version is too old.

    """

    # pylint: disable=R0912
    def __init__(self, filename=None):
        """Default constructor for the FirmwarePackage class."""
        self.images = []
        self.version = None
        self.config = None
        self.required_socman_version = None
        self.work_dir = temp_dir()

        if filename:
            # Extract files and read config
            try:
                tarfile.open(filename, "r").extractall(self.work_dir)
            except (IOError, tarfile.ReadError):
                raise ValueError("%s is not a valid tar.gz file"
                        % os.path.basename(filename))
            config = ConfigParser.SafeConfigParser()

            if len(config.read(self.work_dir + "/MANIFEST")) == 0:
                raise ValueError("%s is not a valid firmware package"
                        % os.path.basename(filename))

            if "package" in config.sections():
                cxmanage_ver = config.get("package",
                        "required_cxmanage_version")
                if sys.platform != 'win32':
                    try:
                        pkg_resources.require("cxmanage>=%s" % cxmanage_ver)
                    except pkg_resources.VersionConflict:
                        # @todo: CxmanageVersionError?
                        raise ValueError(
                                "%s requires cxmanage version %s or later."
                                % (filename, cxmanage_ver))

                if config.has_option("package", "required_socman_version"):
                    self.required_socman_version = config.get("package",
                            "required_socman_version")
                if config.has_option("package", "firmware_version"):
                    self.version = config.get("package", "firmware_version")
                if config.has_option("package", "firmware_config"):
                    self.config = config.get("package", "firmware_config")

            # Add all images from package
            image_sections = [x for x in config.sections() if x != "package"]
            for section in image_sections:
                filename = "%s/%s" % (self.work_dir, section)
                image_type = config.get(section, "type").upper()
                simg = None
                daddr = None
                skip_crc32 = False
                version = None

                # Read image options from config
                if config.has_option(section, "simg"):
                    simg = config.getboolean(section, "simg")
                if config.has_option(section, "daddr"):
                    daddr = int(config.get(section, "daddr"), 16)
                if config.has_option(section, "skip_crc32"):
                    skip_crc32 = config.getboolean(section, "skip_crc32")
                if config.has_option(section, "versionstr"):
                    version = config.get(section, "versionstr")

                self.images.append(Image(filename, image_type, simg, daddr,
                        skip_crc32, version))

    def save_package(self, filename):
        """Save all images as a firmware package.

        .. note::
            * Supports tar .gz and .bz2 file extensions.

        >>> from cxmanage_api.firmware_package import FirmwarePackage
        >>> fwpkg = FirmwarePackage()
        >>> fwpkg.save_package(filename='my_fw_update_pkg.tar.gz')

        :param filename: Name (or path) of of the file you wish to save.
        :type filename: string

        """
        # Create the manifest
        config = ConfigParser.SafeConfigParser()
        for image in self.images:
            section = os.path.basename(image.filename)
            config.add_section(section)
            config.set(section, "type", image.type)
            config.set(section, "simg", str(image.simg))
            if image.priority != None:
                config.set(section, "priority", str(image.priority))
            if image.daddr != None:
                config.set(section, "daddr", "%x" % image.daddr)
            if image.skip_crc32:
                config.set(section, "skip_crc32", str(image.skip_crc32))
            if image.version != None:
                config.set(section, "versionstr", image.version)

        manifest = open("%s/MANIFEST" % self.work_dir, "w")
        config.write(manifest)
        manifest.close()

        # Create the tar.gz package
        if filename.endswith("gz"):
            tar = tarfile.open(filename, "w:gz")
        elif filename.endswith("bz2"):
            tar = tarfile.open(filename, "w:bz2")
        else:
            tar = tarfile.open(filename, "w")

        tar.add("%s/MANIFEST" % self.work_dir, "MANIFEST")
        for image in self.images:
            tar.add(image.filename, os.path.basename(image.filename))
        tar.close()


# End of file: ./firmware_package.py
