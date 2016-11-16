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
import sys
import tempfile
import unittest
from vsc.utils.run import run_simple


FAKE_MPIRUN = """#!/bin/bash
echo 'fake mpirun called with args:' $@
"""

def install_fake_mpirun(cmdname, path, txt=None):
    """Install fake mpirun command with given name in specified location"""
    fake_mpirun = os.path.join(path, cmdname)
    if not txt:
        txt = FAKE_MPIRUN
    open(fake_mpirun, 'w').write(txt)
    os.chmod(fake_mpirun, stat.S_IRUSR|stat.S_IXUSR)
    os.environ['PATH'] = '%s:%s' % (path, os.getenv('PATH', ''))


class TestEnd2End(unittest.TestCase):
    """End-to-end tests for mympirun"""

    def setUp(self):
        """Prepare to run test."""
        self.orig_environ = copy.deepcopy(os.environ)

        # add /bin to $PATH, /lib to $PYTHONPATH
        self.topdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.mympiscript = os.path.join(os.path.join(self.topdir, 'bin'), 'mympirun.py')
        os.environ['PYTHONPATH'] = '%s:%s' % (os.path.join(self.topdir, 'lib'), os.getenv('PYTHONPATH', ''))

        self.tmpdir = tempfile.mkdtemp()

        # make sure we're using the right mympirun installation...
        ec, out = run_simple("%s -c 'import vsc.mympirun; print vsc.mympirun.__file__'" % sys.executable)
        expected_path = os.path.join(self.topdir, 'lib', 'vsc', 'mympirun')
        self.assertTrue(os.path.samefile(os.path.dirname(out.strip()), expected_path))

    def tearDown(self):
        """Clean up after running test."""
        os.environ = self.orig_environ
        shutil.rmtree(self.tmpdir)

    def test_serial(self):
        """Test running of a serial command via mympirun."""
        print os.environ['PATH']

        install_fake_mpirun('mpirun', self.tmpdir)
        ec, out = run_simple("%s %s --setmpi impirun hostname" % (sys.executable, self.mympiscript))
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
        regex = re.compile("^fake mpirun called with args: .*hostname$")

        self.assertTrue(regex.match(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

    def test_sched(self):
        """ Test --sched(type) option """
        install_fake_mpirun('mpirun', self.tmpdir)
        regex_tmpl = "^fake mpirun called with args: .*%s.* hostname$"
        testcases = {
            'impirun': "-genv I_MPI_DEVICE shm",
            'ompirun': "--mca btl sm,.*self",
        }
        for key in testcases:
            ec, out = run_simple("%s %s --setmpi %s --sched local hostname" % (sys.executable, self.mympiscript, key))
            self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
            regex = re.compile(regex_tmpl % testcases[key])
            self.assertTrue(regex.match(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))


    def test_output(self):
        """ Test --output option """
        install_fake_mpirun('mpirun', self.tmpdir, txt=FAKE_MPIRUN + "\necho 'fake mpirun error' >&2")
        f_out = os.path.join(self.tmpdir, "temp.out")

        ec, out = run_simple("%s %s --setmpi impirun --output %s hostname" % (sys.executable, self.mympiscript, f_out))

        self.assertTrue(os.path.isfile(f_out))
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
        self.assertFalse(out, "Found output in stdout/stderr: %s" % out)

        regex = re.compile("^fake mpirun called with args: .* hostname\nfake mpirun error$")

        with open(f_out, 'r') as output:
            text = output.read()
            self.assertTrue(regex.match(text), "Pattern '%s' found in: %s" % (regex.pattern, text))


    def test_hanging(self):
        """ Test --output-check-timeout option when program has no output"""
        no_output_mpirun = '\n'.join([
            "#!/bin/bash",
            "sleep 4",
            "echo 'some output'",
            "sleep 3"
        ])

        install_fake_mpirun('mpirun', self.tmpdir, txt=no_output_mpirun)
        cmd = ' '.join([
            sys.executable,
            self.mympiscript,
            "--setmpi impirun",
            "--output-check-timeout 2",
            "--disable-output-check-fatal",
            "hostname",
            ])
        ec, out = run_simple(cmd)
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))

        regex = re.compile("mympirun has been running for .* seconds without seeing any output.")

        self.assertTrue(len(regex.findall(out)) == 1, "Pattern '%s' found in: %s" % (regex.pattern, out))


    def test_hanging_file(self):
        """ Test --output-check-timeout option when program has no output writing to file"""
        no_output_mpirun = '\n'.join([
            "#!/bin/bash",
            "sleep 4",
            "echo 'some output'",
            "sleep 3"
        ])

        f_out = os.path.join(self.tmpdir, "temp.out")

        install_fake_mpirun('mpirun', self.tmpdir, txt=no_output_mpirun)
        cmd = ' '.join([
            sys.executable,
            self.mympiscript,
            "--setmpi impirun",
            "--output %s" % f_out,
            "--output-check-timeout 2",
            "--disable-output-check-fatal",
            "hostname",
            ])
        ec, out = run_simple(cmd)
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))

        regex = re.compile("mympirun has been running for .* seconds without seeing any output.")
        self.assertTrue(len(regex.findall(out)) == 1, "Pattern '%s' found in: %s" % (regex.pattern, out))


    def test_hanging_fatal(self):
        """Test fatal hanging check when program has no output"""
        no_output_mpirun = '\n'.join([
            "#!/bin/bash",
            "sleep 4",
        ])

        install_fake_mpirun('mpirun', self.tmpdir, txt=no_output_mpirun)
        # fatal is True by default
        cmd = ' '.join([
            sys.executable,
            self.mympiscript,
            "--setmpi impirun",
            "--output-check-timeout 2",
            "hostname",
            ])
        ec, out = run_simple(cmd)
        self.assertEqual(ec, 124)

        regex = re.compile("mympirun has been running for .* seconds without seeing any output.")
        self.assertTrue(len(regex.findall(out)) == 1, "Pattern '%s' found in: %s" % (regex.pattern, out))
