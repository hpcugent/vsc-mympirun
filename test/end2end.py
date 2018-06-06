#
# Copyright 2012-2017 Ghent University
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
import vsc.mympirun.rm.sched as schedm
from vsc.utils.missing import nub
from vsc.utils.run import run

from vsc.mympirun.mpi.mpi import MPI, which
from vsc.mympirun.rm.local import Local
from vsc.mympirun.rm.pbs import PBS
from sched import cleanup_PBS_env, reset_env, set_PBS_env, set_SLURM_env


FAKE_MPIRUN = """#!/bin/bash
echo 'fake mpirun called with args:' $@
while test $# -gt 0
do
    case "$1" in
        -info) echo "    Bootstrap servers available:             ssh rsh pdsh fork slum ll pbsdsh"
            ;;
    esac
    shift
done
"""

FAKE_MPIRUN_MACHINEFILE = r"""#!/bin/bash
if [ "$1" == "-info" ]; then
    echo "    Bootstrap servers available:             ssh rsh pdsh fork slum ll pbsdsh"
else
    machinefile=$(echo $@ | sed -e 's/.*-machinefile[ ]*\([^ ]*\).*/\1/g')
    cat $machinefile
fi
"""

def install_fake_mpirun(cmdname, path, mpi_name, mpi_version, txt=None):
    """Install fake mpirun command with given name in specified location"""
    fake_mpirun = os.path.join(path, cmdname)
    if not txt:
        txt = FAKE_MPIRUN
    open(fake_mpirun, 'w').write(txt)
    os.chmod(fake_mpirun, stat.S_IRUSR|stat.S_IXUSR)
    os.environ['PATH'] = '%s:%s' % (path, os.getenv('PATH', ''))
    os.environ['EBROOT%s' % mpi_name.upper()] = os.path.dirname(fake_mpirun)
    os.environ['EBVERSION%s' % mpi_name.upper()] = mpi_version


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

        # add location of symlink 'pbsssh' to actual pbsssh.sh script to $PATH too
        os.mkdir(os.path.join(self.tmpdir, 'bin'))
        os.symlink(os.path.join(self.topdir, 'bin', 'pbsssh.sh'), os.path.join(self.tmpdir, 'bin', 'pbsssh'))
        os.environ['PATH'] = '%s:%s' % (os.path.join(self.tmpdir, 'bin'), os.getenv('PATH', ''))

        # make sure we're using the right mympirun installation...
        ec, out = run([sys.executable, '-c', "import vsc.mympirun; print vsc.mympirun.__file__"])
        out = out.strip()
        expected_path = os.path.join(self.topdir, 'lib', 'vsc', 'mympirun')
        self.assertTrue(os.path.samefile(os.path.dirname(out), expected_path), "%s not in %s" % (out, expected_path))

        # set variables that exist within jobs, but not locally, for testing
        self.tmpdir = tempfile.mkdtemp()
        pbs_tmpdir = os.path.join(self.tmpdir, 'pbs')
        os.makedirs(pbs_tmpdir)
        set_PBS_env(pbs_tmpdir)

    def tearDown(self):
        """Clean up after running test."""
        cleanup_PBS_env()
        os.chmod(self.tmpdir, stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)
        shutil.rmtree(self.tmpdir)
        reset_env(self.orig_environ)

    def test_serial(self):
        """Test running of a serial command via mympirun."""

        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2')
        ec, out = run([sys.executable, self.mympiscript, 'hostname'])
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
        regex = re.compile("^fake mpirun called with args: .*hostname$")

        self.assertTrue(regex.match(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

    def test_sched(self):
        """ Test --sched(type) option """
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2')
        regex_tmpl = "^fake mpirun called with args: .*%s.* hostname$"
        testcases = {
            'impirun': "-genv I_MPI_DEVICE 'shm'",
            'ompirun': "--mca btl 'sm,.*self'",
        }
        for key in testcases:
            ec, out = run([sys.executable, self.mympiscript, '--setmpi', key, '--sched', 'local', 'hostname'])
            self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
            regex = re.compile(regex_tmpl % testcases[key])
            self.assertTrue(regex.match(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))


    def test_output(self):
        """ Test --output option """
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=FAKE_MPIRUN + "\necho 'fake mpirun error' >&2")
        f_out = os.path.join(self.tmpdir, "temp.out")

        ec, out = run([sys.executable, self.mympiscript, '--output', f_out, 'hostname'])

        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))
        self.assertFalse(out, "Found output in stdout/stderr: %s" % out)
        self.assertTrue(os.path.isfile(f_out))

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

        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=no_output_mpirun)
        cmd = [
            sys.executable,
            self.mympiscript,
            '--output-check-timeout', '2',
            'hostname',
        ]
        ec, out = run(cmd)
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

        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=no_output_mpirun)
        cmd = [
            sys.executable,
            self.mympiscript,
            '--output', f_out,
            '--output-check-timeout', '2',
            'hostname',
        ]
        ec, out = run(cmd)
        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))

        regex = re.compile("mympirun has been running for .* seconds without seeing any output.")
        self.assertTrue(len(regex.findall(out)) == 1, "Pattern '%s' found in: %s" % (regex.pattern, out))


    def test_hanging_fatal(self):
        """Test fatal hanging check when program has no output"""
        no_output_mpirun = '\n'.join([
            "#!/bin/bash",
            "sleep 4",
        ])

        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=no_output_mpirun)
        cmd = [
            sys.executable,
            self.mympiscript,
            '--output-check-fatal',
            '--output-check-timeout', '2',
            'hostname',
        ]
        ec, out = run(cmd)
        self.assertEqual(ec, 124)

        regex = re.compile("mympirun has been running for .* seconds without seeing any output.")
        self.assertTrue(len(regex.findall(out)) == 1, "Pattern '%s' found in: %s" % (regex.pattern, out))


    def test_option_double(self):
        """Test --double command line option"""
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=FAKE_MPIRUN_MACHINEFILE)
        ec, out = run([sys.executable, self.mympiscript, '--double', 'hostname'])
        # set_pbs_env() sets 2 cores, so double is 4
        self.assertEqual(out, ('\n'.join(['localhost'] * 4)))
        self.assertEqual(len(out.split('\n')), 4)


    def test_option_multi(self):
        """Test --multi command line option"""
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=FAKE_MPIRUN_MACHINEFILE)
        ec, out = run([sys.executable, self.mympiscript, '--multi', '3', '--', 'hostname'])
        # set_pbs_env() sets 2 cores, so *3 = 6
        self.assertEqual(out, ('\n'.join(['localhost'] * 6)))
        self.assertEqual(len(out.split('\n')), 6)


    def test_option_hybrid(self):
        """Test --hybrid command line option"""
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=FAKE_MPIRUN_MACHINEFILE)
        ec, out = run([sys.executable, self.mympiscript, '--hybrid', '5', 'hostname'])
        self.assertEqual(out, ('\n'.join(['localhost'] * 5)))
        self.assertEqual(len(out.split('\n')), 5)


    def test_option_universe(self):
        """Test --universe command line option"""
        # test with Intel MPI versions where mpd & hydra as the default process managers
        for impi_ver in ['4.0.3', '4.2', '5.1.2']:

            mpirun = os.path.join(self.tmpdir, 'mpirun')
            if os.path.exists(mpirun):
                os.remove(mpirun)
            install_fake_mpirun('mpirun', self.tmpdir, 'impi', impi_ver)

            self.change_env(5)
            ec, out = run([sys.executable, self.mympiscript, '--universe', '4', 'hostname'])
            self.assertEqual(ec, 0)
            regex = re.compile('-np 4')
            self.assertTrue(regex.search(out))

            self.change_env(1)
            # intel mpi without hydra
            os.environ['I_MPI_PROCESS_MANAGER'] = 'mpd'
            ec, out = run([sys.executable, self.mympiscript, '--universe', '1', 'hostname'])
            self.assertEqual(ec, 0)

            np_regex = re.compile('-np 1')
            ncpus_regex = re.compile('--ncpus=1')
            self.assertTrue(np_regex.search(out))
            self.assertTrue(ncpus_regex.search(out))

            del os.environ['I_MPI_PROCESS_MANAGER']

    def test_option_universe_hydra(self):
        """Test --universe command line option with hydra impi"""
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.124.67')

        cmd = "%s %s --universe 1 hostname"
        ec, out = run([sys.executable, self.mympiscript, '--universe', '1', 'hostname'])

        np_regex = re.compile('-np 1')
        ncpus_regex = re.compile('--ncpus=1')
        self.assertTrue(np_regex.search(out), "Pattern %s found in %s" % (np_regex, out))
        self.assertFalse(ncpus_regex.search(out), "Pattern %s found in %s" % (ncpus_regex, out))

    def test_env_variables(self):
        """ Test the passing of (extra) variables """
        fake_mpirun_env = """#!/bin/bash
        echo 'fake mpirun called with args:' $@
        env
        """
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2', txt=fake_mpirun_env)

        os.environ['PYTHONPATH'] = '/just/an/example:%s' % os.getenv('PYTHONPATH', '')

        command = [
            sys.executable,
            self.mympiscript,
            "--variablesprefix=USER",
            "hostname",
        ]
        ec, out = run(command)

        for key in nub(filter(os.environ.has_key, MPI.OPTS_FROM_ENV_BASE)):
            self.assertTrue(key in out, "%s is not in out" % key)

        regex = r'.*-envlist [^ ]*USER.*'
        self.assertTrue(re.search(regex, out), "Variablesprefix USER isn't passed to mympirun script env")

        regex = r'PYTHONPATH=/just/an/example:.*'
        self.assertTrue(re.search(regex, out), "PYTHONPATH isn't passed to mympirun script env correctly: %s" % out)

    def change_env(self, cores):
        """Helper method for changing the number of cores in the machinefile"""
        os.chmod(os.environ['PBS_NODEFILE'], stat.S_IWUSR)
        pbsnodefile = open(os.environ['PBS_NODEFILE'], 'w')
        pbsnodefile.write('\n'.join(['localhost'] * cores))
        pbsnodefile.close()
        os.chmod(os.environ['PBS_NODEFILE'], stat.S_IRUSR)

    def test_unset_nodefile(self):
        """ Test if sched falls back to Local if nodefile is not available """
        self.assertEqual(schedm.what_sched(False)[0], PBS)
        nodefile = os.environ['PBS_NODEFILE']
        del os.environ['PBS_NODEFILE']
        # fall back to local if PBS_NODEFILE is not available
        self.assertEqual(schedm.what_sched(False)[0], Local)
        # restore env
        os.environ['PBS_NODEFILE'] = nodefile

    def test_launcher_opt_old_impi(self):
        """Test --launcher command line option with impi < 5.0.3"""

        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '4.2')

        ec, out = run([sys.executable, self.mympiscript, 'hostname'])
        regex = r'-bootstrap ssh'
        self.assertTrue(re.search(regex, out), "-bootstrap option is not ssh (default for impi/4.2)" + out)

    def test_launcher_opt_impi_hydra(self):
        """Test --launcher command line option with impi >= 5.0.3 (supports pbsdsh)"""
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.0.3')

        # default behavior
        ec, out = run([sys.executable, self.mympiscript, 'hostname'])
        regex = r'-bootstrap pbsdsh'
        self.assertTrue(re.search(regex, out), "-bootstrap option is pbsdsh (default for impi/5.1): " + out)

        # if --launcher ssh is used, behaviour depends on whether or not pbsdsh are available
        ec, out = run([sys.executable, self.mympiscript, '--launcher', 'ssh', 'hostname'])

        regexes = [
            (r'-bootstrap ssh', "bootstrap option is ssh (possibly with -bootstrap-exec option)"),
        ]
        pbsdsh = which('pbsdsh')
        if pbsdsh:
            # '-bootstrap-exec pbsssh' is used only when pbsdsh is available
            regexes.append((r'-bootstrap-exec pbsssh', "pbsssh is used when launcher is ssh and pbsdsh is there"))
        else:
            # withtout pbsdsh, no -bootstrap-exec
            fail_msg = "No -bootstrap-exec option when launcher is ssh and no pbsdsh: %s" % out
            self.assertFalse(re.search(r'-bootstrap-exec', out), fail_msg)

        for regex in regexes:
            self.assertTrue(re.search(regex[0], out), regex[1] + ": " + out)

        # unknown launcher being specified only results in a warning (we allow specifying launchers that are not listed)
        ec, out = run([sys.executable, self.mympiscript, '--launcher', 'doesnotexist', 'hostname'])
        regex = r'WARNING .* Specified launcher doesnotexist does not exist'
        self.assertTrue(re.search(regex, out), "mympirun should warn for non-existing launcher")

        ec, out = run([sys.executable, self.mympiscript, '--sched', 'local', 'hostname'])
        self.assertFalse("-bootstrap" in out, "using local scheduler, no bootstrap launcher should be specified: " + out)


    def test_launcher_opt_ompi(self):
        """Test ompi v 2.0 bug (mympirun should produce error and stop)"""
        install_fake_mpirun('mpirun', self.tmpdir, 'openmpi', '2.0')
        ec, out = run([sys.executable, self.mympiscript, 'hostname'])
        self.assertEqual(ec, 1)
        regex = r"OpenMPI 2\.0\.x uses a different naming protocol for nodes"
        self.assertTrue(re.search(regex, out), "mympirun should produce an error with ompi 2.0: %s" % out)

    def test_dry_run(self):
        """Test use of --dry-run/-D option."""
        install_fake_mpirun('mpirun', self.tmpdir, 'impi', '5.1.2')

        for dry_run_opt in ['--dry-run', '-D']:
            ec, out = run([sys.executable, self.mympiscript, dry_run_opt, 'hostname'])
            self.assertEqual(ec, 0)

            regex = re.compile('^mpirun .* hostname$')
            self.assertTrue(regex.search(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

            extra_opts = ['--hybrid', '9']
            ec, out = run([sys.executable, self.mympiscript, dry_run_opt] + extra_opts + ['hostname'])
            self.assertEqual(ec, 0)

            regex = re.compile('^mpirun .* -np 9 .* hostname$')
            self.assertTrue(regex.search(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

    def test_openmpi_slurm(self):
        """Test running mympirun with OpenMPI in a SLURM environment."""
        set_SLURM_env(self.tmpdir)

        os.environ['SLURM_TASKS_PER_NODE'] = '2'
        # patch scontrol to spit out "localhost" hostnames
        scontrol = os.path.join(self.tmpdir, 'scontrol')
        os.chmod(scontrol, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        fh = open(scontrol, 'w')
        fh.write("#!/bin/bash\necho localhost")
        fh.close()

        install_fake_mpirun('mpirun', self.tmpdir, 'openmpi', '2.1', txt=FAKE_MPIRUN + "\nenv | sort")
        ec, out = run([sys.executable, self.mympiscript, 'hostname'])

        self.assertEqual(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))

        # make sure output includes defined environment variables
        # and "--mca orte_keep_fqdn_hostnames '1'"
        mca_keep_fqdn = "^fake mpirun called with args:.*--mca orte_keep_fqdn_hostnames '1'.*hostname$"
        for pattern in ['^HOME=', '^USER=', '^SLURM_JOBID=', mca_keep_fqdn]:
            regex = re.compile(pattern, re.M)
            self.assertTrue(regex.search(out), "Pattern '%s' found in: %s" % (regex.pattern, out))

        # $SLURM_EXPORT_ENV should no longer be defined in environment
        regex = re.compile('SLURM_EXPORT_ENV', re.M)
        self.assertFalse(regex.search(out), "Pattern '%s' *not* found in: %s" % (regex.pattern, out))
