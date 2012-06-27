import os
import shutil
import tempfile
import unittest

from cxmanage.tftp import InternalTftp, ExternalTftp

from cxmanage_test import random_file

class InternalTftpTest(unittest.TestCase):
    """ Tests involving an internal TFTP server """

    def setUp(self):
        self.work_dir = tempfile.mkdtemp()
        self.tftp = InternalTftp()

    def tearDown(self):
        shutil.rmtree(self.work_dir)
        self.tftp.kill()

    def test_put_and_get(self):
        """ Test file transfers on an internal host """

        # Create file
        filename = random_file(self.work_dir, 1024)
        contents = open(filename).read()

        # Upload and remove
        basename = os.path.basename(filename)
        self.tftp.put_file(filename, basename)
        os.remove(filename)
        self.assertFalse(os.path.exists(filename))

        # Download
        self.tftp.get_file(basename, filename)

        # Verify match
        self.assertEqual(open(filename).read(), contents)

class ExternalTftpTest(unittest.TestCase):
    """ Tests involving an external TFTP server.

    For testing purposes the 'external' server points to an internally hosted
    one, but it allows us to make sure the actual TFTP protocol is working. """

    def setUp(self):
        self.work_dir = tempfile.mkdtemp()

        # Set up an internal server
        self.internal_tftp = InternalTftp()

        # Set up external server
        address = "localhost"
        port = self.internal_tftp.get_port()
        self.tftp = ExternalTftp(address, port)

    def tearDown(self):
        shutil.rmtree(self.work_dir)
        self.internal_tftp.kill()

    def test_put_and_get(self):
        """ Test file transfers on an external host """

        # Create file
        filename = random_file(self.work_dir, 1024)
        contents = open(filename).read()

        # Upload and remove original file
        basename = os.path.basename(filename)
        self.tftp.put_file(filename, basename)
        os.remove(filename)
        self.assertFalse(os.path.exists(filename))

        # Download
        self.tftp.get_file(basename, filename)

        # Verify match
        self.assertEqual(open(filename).read(), contents)