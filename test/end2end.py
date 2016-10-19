#
# Copyright 2012-2016 Ghent University
#
# This file is part of vsc-mympirun,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# the Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/hpcugent/vsc-mympirun
#
# vsc-mympirun is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# vsc-mympirun is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with vsc-mympirun.  If not, see <http://www.gnu.org/licenses/>.
#
"""
End-to-end tests for mympirun (with mocking of real 'mpirun' command).

@author: Jeroen De Clerck (HPC-UGent)
@author: Kenneth Hoste (HPC-UGent)
@author: Caroline De Brouwer (HPC-UGent)
"""
import copy
import os
import re
import shutil
import stat
import tempfile
import unittest
from vsc.utils.run import run_simple


FAKE_MPIRUN = """#!/bin/bash
echo 'fake mpirun called with args:' $@
"""

def install_fake_mpirun(txt, cmdname, path):
    """Install fake mpirun command with given name in specified location"""
    fake_mpirun = os.path.join(path, cmdname)
    open(fake_mpirun, 'w').write(txt)
    os.chmod(fake_mpirun, stat.S_IRUSR|stat.S_IXUSR)
    os.environ['PATH'] = '%s:%s' % (path, os.getenv('PATH', ''))


class TestEnd2End(unittest.TestCase):
    """End-to-end tests for mympirun"""

    def setUp(self):
        """Prepare to run test."""
        self.orig_environ = copy.deepcopy(os.environ)

        # add /bin to $PATH, /lib to $PYTHONPATH
        topdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.environ['PATH'] = '%s:%s' % (os.path.join(topdir, 'bin'), os.getenv('PATH', ''))
        os.environ['PYTHONPATH'] = '%s:%s' % (os.path.join(topdir, 'lib'), os.getenv('PYTHONPATH', ''))

        self.tmpdir = tempfile.mkdtemp()

        # make sure we're using the right mympirun installation...
        ec, out = run_simple("python -c 'import vsc.mympirun; print vsc.mympirun.__file__'")
        expected_path = os.path.join(topdir, 'lib', 'vsc', 'mympirun')
        self.assertTrue(os.path.samefile(os.path.dirname(out.strip()), expected_path))

    def tearDown(self):
        """Clean up after running test."""
        os.environ = self.orig_environ
        shutil.rmtree(self.tmpdir)

    def test_serial(self):
        """Test running of a serial command via mympirun."""
        print os.environ['PATH']

        install_fake_mpirun(FAKE_MPIRUN, 'mpirun', self.tmpdir)
        ec, out = run_simple("mympirun.py --setmpi impirun hostname$")
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
        regex = re.compile("^fake mpirun called with args: .*hostname")
        self.assertTrue(regex.match(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

    def test_sched(self):
        """ Test --sched(type) option """
        install_fake_mpirun(FAKE_MPIRUN, 'mpirun', self.tmpdir)
        regex_tmpl = "^fake mpirun called with args: .*%s.* hostname$"
        testcases = {
            'impirun': "-genv I_MPI_DEVICE shm",
            'ompirun': "--mca btl sm,.*self",
        }
        for key in testcases:
            ec, out = run_simple("mympirun.py --setmpi %s --sched local hostname" % key)
            self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
            regex = re.compile(regex_tmpl % testcases[key])
            self.assertTrue(regex.match(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

    def test_output(self):
        """ Test --output option """
        mpirun_error = """#!/bin/bash
                          echo 'fake mpirun called with args:' $@

                          >&2 echo 'fake mpirun error'
                       """

        install_fake_mpirun(mpirun_error, 'mpirun', self.tmpdir)
        f_out = os.path.join(self.tmpdir, "temp.out")

        ec, out = run_simple("mympirun.py --setmpi impirun --output %s hostname" % f_out)

        self.assertTrue(os.path.isfile(f_out))
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
        self.assertFalse(out, "Found output in stdout/stderr: %s" % out)

        regexes = [
            re.compile("^fake mpirun called with args: .* hostname\nfake mpirun error$"),
        ]

        with open(f_out, 'r') as output:
            text = output.read()
            for regex in regexes:
                self.assertTrue(regex.match(text), "Pattern '%s' found in: %s" % (regex.pattern, text))

