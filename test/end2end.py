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
import glob
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from vsc.utils.missing import nub
from vsc.utils.run import run_simple

from vsc.mympirun.mpi.mpi import MPI
from sched import set_PBS_env, cleanup_PBS_env


FAKE_MPIRUN = """#!/bin/bash
echo 'fake mpirun called with args:' $@
"""

FAKE_MPIRUN_MACHINEFILE = r"""#!/bin/bash
machinefile=$(echo $@ | sed -e 's/.*-machinefile[ ]*\([^ ]*\).*/\1/g')
cat $machinefile
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
        lib = os.path.join(self.topdir, 'lib')
        # make sure subshell finds .egg files by adding them to the pythonpath
        eggs = ':'.join(glob.glob(os.path.join(self.topdir, '.eggs', '*.egg')))
        os.environ['PYTHONPATH'] = '%s:%s:%s' % (eggs, lib, os.getenv('PYTHONPATH', ''))
        self.tmpdir = tempfile.mkdtemp()
        os.environ['HOME'] = self.tmpdir
        mpdconf = open(os.path.join(self.tmpdir, '.mpd.conf'), 'w')
        mpdconf.write("password=topsecretpassword")
        mpdconf.close()

        # make sure we're using the right mympirun installation...
        ec, out = run_simple("%s -c 'import vsc.mympirun; print vsc.mympirun.__file__'" % sys.executable)
        expected_path = os.path.join(self.topdir, 'lib', 'vsc', 'mympirun')
        self.assertTrue(os.path.samefile(os.path.dirname(out.strip()), expected_path))
        # set variables that exist within jobs, but not locally, for testing
        set_PBS_env()

    def tearDown(self):
        """Clean up after running test."""
        cleanup_PBS_env(self.orig_environ)
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

        regex = re.compile(("mympirun has been running for .* seconds without seeing any output.\n"
                            "This may mean that your program is hanging, please check and make sure that is not the case!"))

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
        # --output-check-fatal is True by default
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


    def test_option_double(self):
        """Test --double command line option"""
        install_fake_mpirun('mpirun', self.tmpdir, txt=FAKE_MPIRUN_MACHINEFILE)
        cmd = "%s %s --setmpi impirun --double hostname"
        ec, out = run_simple(cmd % (sys.executable, self.mympiscript))
        # set_pbs_env() sets 2 cores, so double is 4
        self.assertEqual(len(out.split('\n')), 4)
        self.assertEqual(out, ('\n'.join(['localhost'] * 4)))


    def test_option_hybrid(self):
        """Test --hybrid command line option"""
        install_fake_mpirun('mpirun', self.tmpdir, txt=FAKE_MPIRUN_MACHINEFILE)
        ec, out = run_simple("%s %s --setmpi impirun --hybrid 5 hostname" % (sys.executable, self.mympiscript))
        self.assertEqual(len(out.split('\n')), 5)
        self.assertEqual(out, ('\n'.join(['localhost'] * 5)))


    def test_option_universe(self):
        """Test --universe command line option"""
        install_fake_mpirun('mpirun', self.tmpdir)

        self.change_env(5)
        ec, out = run_simple("%s %s --setmpi impirun --universe 4 hostname" % (sys.executable, self.mympiscript))
        regex = re.compile('-np 4')
        self.assertTrue(regex.search(out))

        self.change_env(1)
        # intel mpi without hydra
        ec, out = run_simple("%s %s --setmpi impirun --universe 1 hostname" % (sys.executable, self.mympiscript))
        os.environ['I_MPI_PROCESS_MANAGER'] = 'mpd'

        np_regex = re.compile('-np 1')
        ncpus_regex = re.compile('--ncpus=1')
        self.assertTrue(np_regex.search(out))
        self.assertTrue(ncpus_regex.search(out))

        # intel mpi with hydra
        del os.environ['I_MPI_PROCESS_MANAGER']
        ec, out = run_simple("%s %s --setmpi ihmpirun --universe 1 hostname" % (sys.executable, self.mympiscript))
        self.assertTrue(np_regex.search(out))
        self.assertFalse(ncpus_regex.search(out))

        # re-set pbs environment
        set_PBS_env()


    def test_env_variables(self):
        """ Test the passing of (extra) variables """
        fake_mpirun_env = """#!/bin/bash
        echo 'fake mpirun called with args:' $@
        env
        """
        install_fake_mpirun('mpirun', self.tmpdir, txt=fake_mpirun_env)
        command = ' '.join([
            sys.executable,
            self.mympiscript,
            "--setmpi impirun",
            "--variablesprefix=USER",
            "hostname",
        ])
        ec, out = run_simple(command)

        for key in nub(filter(os.environ.has_key, MPI.OPTS_FROM_ENV_BASE)):
            self.assertTrue(key in out, "%s is not in out" % key)

        regex = r'.*-envlist [^ ]*USER.*'
        self.assertTrue(regex.find(out), "Variablesprefix USER isn't passed to mympirun script env")

        if os.environ.has_key('PYTHONPATH'):
            regex = r'.*-envlist [^ ]*PYTHONPATH.*'
            self.assertTrue(regex.find(out), "PYTHONPATH isn't passed to mympirun script env")



    def change_env(self, cores):
        """Helper method for changing the number of cores in the machinefile"""
        pbsnodefile = tempfile.NamedTemporaryFile(delete=False)
        pbsnodefile.write('\n'.join(['localhost'] * cores))
        pbsnodefile.close()
        os.environ['PBS_NODEFILE'] = pbsnodefile.name


