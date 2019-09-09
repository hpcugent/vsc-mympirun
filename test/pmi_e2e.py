#
# Copyright 2019-2019 Ghent University
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
End-to-end tests for mypmirun
"""

import logging
logging.basicConfig(level=logging.DEBUG)

import copy
import glob
import os
import re
import tempfile
import shutil
import sys
import tempfile
from vsc.install.testing import TestCase
from vsc.utils.run import run

from sched import reset_env
from mock import patch

from vsc.mympirun.main import get_mpi_and_sched_and_options
from vsc.mympirun.factory import getinstance

import vsc.mympirun.pmi.mpi as mpim
import vsc.mympirun.pmi.sched as schedm
from vsc.mympirun.pmi.option import MympirunOption as mpiopt


SLURM_2NODES = """
SLURM_CPUS_ON_NODE=32
SLURM_JOB_CPUS_PER_NODE=32(x2)
SLURM_JOB_ID=123456
SLURM_JOB_NODELIST=node[3302-3303]
SLURM_JOB_NUM_NODES=2
SLURM_MEM_PER_CPU=7600
SLURM_NNODES=2
SLURM_NPROCS=64
SLURM_NTASKS=64
"""

class PMITest(TestCase):
    def setUp(self):
        """Prepare to run test."""
        super(PMITest, self).setUp()

        self.orig_environ = copy.deepcopy(os.environ)

        # add /bin to $PATH, /lib to $PYTHONPATH
        self.topdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.script = os.path.join(os.path.join(self.topdir, 'bin'), 'mypmirun.py')
        lib = os.path.join(self.topdir, 'lib')
        # make sure subshell finds .egg files by adding them to the pythonpath
        eggs = ':'.join(glob.glob(os.path.join(self.topdir, '.eggs', '*.egg')))
        os.environ['PYTHONPATH'] = '%s:%s:%s' % (eggs, lib, os.getenv('PYTHONPATH', ''))

        # make sure we're using the right mympirun installation...
        ec, out = run([sys.executable, '-c', "import vsc.mympirun; print vsc.mympirun.__file__"])
        out = out.strip()
        expected_path = os.path.join(self.topdir, 'lib', 'vsc', 'mympirun')
        self.assertTrue(os.path.samefile(os.path.dirname(out), expected_path), "%s not in %s" % (out, expected_path))

        self.which_patcher = patch('vsc.mympirun.common.which')
        self.mock_which = self.which_patcher.start()

        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after running test."""
        self.which_patcher.stop()
        reset_env(self.orig_environ)
        shutil.rmtree(self.tmpdir)

        super(PMITest, self).tearDown()

    def eb(self, name, version):
        """setup EB for name/version"""
        root = os.path.join(self.tmpdir, name, version)
        os.environ['EBROOT'+name.upper()] = root
        os.environ['EBVERSION'+name.upper()] = version
        return root

    def set_mpi(self, name, version):
        """set mpi enviroment"""
        root = self.eb(name, version)
        mpirun = os.path.join(root, "bin", "mpirun")
        self.mock_which.return_value = mpirun
        return mpirun

    def set_env(self, env):
        if isinstance(env, basestring):
            for line in env.split("\n"):
                if '=' in line:
                    os.environ.update(dict([line.strip().split("=", 1)]))
        else:
            os.environ.update(env)

    def set_slurm_ompi4_ucx(self, env):
        self.set_env(env)
        self.set_mpi('OpenMPI', '4.0.1')
        self.eb('ucx', '1.2.3')

    def get_instance(self):
        opts = get_mpi_and_sched_and_options(mpim, mpiopt, schedm)
        instance = getinstance(*opts)

        return instance


class PMISimple(PMITest):
    def test_pmitest(self):
        """Test the PMITest class"""
        self.set_slurm_ompi4_ucx(SLURM_2NODES)
        mpr = self.get_instance()

        self.assertEqual(mpr.LAUNCHER, 'srun', 'srun launcher')
        self.assertEqual(mpr.PMI[0].FLAVOUR, 'pmix', 'pmix flavour')


class PMIEnd2End(PMITest):
    def set_mpi(self, name, version):
        mpirun = super(PMIEnd2End, self).set_mpi(name, version)

        # can't mock which in end2end
        path = os.path.dirname(mpirun)
        os.environ['PATH'] = "%s:%s" % (path, os.environ['PATH'])
        if not os.path.exists(path):
            os.makedirs(path)

        os.symlink(os.path.join(self.topdir, 'test', 'mpirun'), mpirun)

    def pmirun(self, args, ok=True, pattern=None):
        """run script"""
        ec, out = run([sys.executable, self.script] + args)
        if ok:
            test = self.assertEqual
        else:
            test = self.assertNotEqual
        test(ec, 0, "Command exited normally: exit code %s; output: %s" % (ec, out))

        if pattern is not None:
            regex = re.compile(pattern)
            self.assertTrue(regex.search(out.strip()), "Pattern '%s' found in: %s" % (regex.pattern, out))

    def test_simple(self):
        self.set_slurm_ompi4_ucx(SLURM_2NODES)

        self.pmirun(['--showmpi', '--debug'], pattern='Found MPI classes OpenMPI4$')
        self.pmirun(['--showsched', '--debug'], pattern='Found Sched classes Slurm$')

    def test_ompi4_slurm(self):
        self.set_slurm_ompi4_ucx(SLURM_2NODES)

        pattern = '--chdir=' + os.getcwd()
        pattern += ' --nodes=2 --ntasks=64 --cpus-per-task=1 --mem-per-cpu=7600'
        pattern += ' --export=ALL --mpi=pmix_v3 --output=xyz --abc=123 --def=456'
        self.pmirun(['--debug', '--output=xyz', '--pass=abc=123,def=456', 'arg1', 'arg2'],
                    pattern=pattern+' arg1 arg2$')
