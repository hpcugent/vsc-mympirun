#
# Copyright 2012-2019 Ghent University
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
Tests for the vsc.mympirun.mpi.sched module.

@author: Jeroen De Clerck
@author: Caroline De Brouwer
@author: Kenneth Hoste
"""
import copy
import os
import shutil
import stat
import tempfile
import unittest
from vsc.utils.missing import nub

from vsc.mympirun.factory import getinstance
import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.option import MympirunOption
import vsc.mympirun.rm.sched as schedm
from vsc.mympirun.rm.local import Local
from vsc.mympirun.rm.pbs import PBS
from vsc.mympirun.rm.scoop import Scoop
from vsc.mympirun.rm.slurm import SLURM


SCHEDDICT = {
    'local': Local,
    'pbs': PBS,
    'scoop': Scoop,
    'slurm': SLURM,
}


def set_PBS_env(tmpdir, nodes=None):
    """Set up the PBS environment to recreate being in a hpc job."""

    pbsnodefile = os.path.join(tmpdir, 'pbsnodefile')
    fh = open(pbsnodefile, 'w')
    if nodes:
        fh.write('\n'.join(nodes))
    else:
        fh.write("localhost\nlocalhost\n")
    fh.close()
    os.environ['PBS_NODEFILE'] = pbsnodefile
    # make $PBS_NODEFILE and directory it is in read-only, just like in the real world
    os.chmod(pbsnodefile, stat.S_IRUSR)
    # make location directory where $PBS_NODEFILE resides read-only
    os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)

    os.environ['PBS_JOBID'] = '12345'
    os.environ['PBS_NUM_PPN'] = '12345'


def cleanup_PBS_env():
    """Clean up $PBS_NODEFILE in mocked PBS environment."""
    pbs_nodefile = os.environ.get('PBS_NODEFILE')
    if pbs_nodefile and os.path.exists(pbs_nodefile):
        os.chmod(pbs_nodefile, stat.S_IWUSR)
        os.chmod(os.path.dirname(pbs_nodefile), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        os.remove(pbs_nodefile)


def set_SLURM_env(tmpdir):
    """Set up the PBS environment to recreate being in a hpc job."""
    os.environ['SLURM_JOBID'] = '12345'
    os.environ['SLURM_NODELIST'] = 'node[1-3]'
    os.environ['SLURM_TASKS_PER_NODE'] = '2,1(x2)'
    os.environ['SLURM_EXPORT_ENV'] = 'NONE'

    scontrol = os.path.join(tmpdir, 'scontrol')
    fh = open(scontrol, 'w')
    fh.write("#!/bin/bash\necho node1\necho node2\necho node3\n")
    fh.close()

    os.chmod(scontrol, stat.S_IRUSR | stat.S_IXUSR)
    os.environ['PATH'] = '%s:%s' % (tmpdir, os.environ.get('PATH', ''))


def reset_env(orig_env):
    """Reset environment to provided original environment."""
    for key in nub(os.environ.keys() + orig_env.keys()):
        orig_val = orig_env.get(key)
        if orig_val is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = orig_env[key]


class TestSched(unittest.TestCase):
    """tests for vsc.mympirun.mpi.sched functions"""

    def setUp(self):
        """Set up test"""
        self.orig_environ = copy.deepcopy(os.environ)
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after running test."""
        cleanup_PBS_env()
        reset_env(self.orig_environ)
        shutil.rmtree(self.tmpdir)

    def test_what_sched(self):
        """Test what_sched function."""

        expected_found_sched = [SLURM, Local, PBS, Scoop]

        # if scheduler is specified, then just return corresponding class
        for key, val in SCHEDDICT.iteritems():
            sched, found_sched = schedm.what_sched(key)
            self.assertEqual(sched, val)
            self.assertEqual(found_sched, expected_found_sched)

        # ensure 'clean' environment
        for key in ['PBS_JOBID', 'PBS_NODEFILE', 'SLURM_JOBID', 'SLURM_NODELIST']:
            if key in os.environ:
                del os.environ[key]

        # if scheduler is not specified, environment determines which scheduler is selected

        # if not in PBS/SLURM environment, local scheduler is used
        sched, found_sched = schedm.what_sched(None)
        self.assertEqual(sched, Local)
        self.assertEqual(found_sched, expected_found_sched)

        # if PBS environment variables are set, use PBS scheduler
        os.environ['PBS_JOBID'] = '12345'
        os.environ['PBS_NODEFILE'] = '/tmp/12345.pbs_nodefile'
        sched, found_sched = schedm.what_sched(None)
        self.assertEqual(sched, PBS)
        self.assertEqual(found_sched, expected_found_sched)

        # if SLURM environment variables are set, use SLURM scheduler
        # (even when PBS environment variables are also set)
        os.environ['SLURM_JOBID'] = '98765'
        os.environ['SLURM_NODELIST'] = 'node[100-102]'
        sched, found_sched = schedm.what_sched(None)
        self.assertEqual(sched, SLURM)
        self.assertEqual(found_sched, expected_found_sched)

        del os.environ['PBS_JOBID']
        del os.environ['PBS_NODEFILE']
        sched, found_sched = schedm.what_sched(None)
        self.assertEqual(sched, SLURM)
        self.assertEqual(found_sched, expected_found_sched)

    def test_get_id(self):
        """
        test if get_id correctly sets inst.sched_id

        get_id gets called by the __init__ of getinstance()
        """
        for key, val in SCHEDDICT.iteritems():
            if key == 'pbs':
                set_PBS_env(self.tmpdir)
            elif key == 'slurm':
                set_SLURM_env(self.tmpdir)

            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertTrue(inst.sched_id == os.environ.get(inst.SCHED_ENVIRON_ID, None) or
                            inst.sched_id.startswith("SCHED_%s" % inst.__class__.__name__))

    def test_core_on_this_node(self):
        """
        test if core_on_this_node() sets cores_per_node to an integer

        core_on_this_node() gets called by the __init__ of getinstance()
        """
        for key, val in SCHEDDICT.iteritems():
            if key == 'pbs':
                set_PBS_env(self.tmpdir)
            elif key == 'slurm':
                set_SLURM_env(self.tmpdir)

            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertTrue(isinstance(inst.cores_per_node, int))

    def test_which_cpus(self):
        """
        test if which_cpus() sets cpus to a list of unique integers

        which_cpus() gets called by the __init__ of getinstance()
        """
        for key, val in SCHEDDICT.iteritems():
            if key == 'pbs':
                set_PBS_env(self.tmpdir)
            elif key == 'slurm':
                set_SLURM_env(self.tmpdir)

            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertTrue(all(isinstance(item, int) for item in inst.cpus) and len(inst.cpus) == len(set(inst.cpus)))

    def test_get_node_list(self):
        """
        test if get_node_list() correctly sets nodes and nrnodes

        get_node_list() gets called by the __init__ of getinstance()
        """
        inst = getinstance(mpim.MPI, Local, MympirunOption())
        self.assertEqual(set(inst.nodes), set(['localhost']))
        self.assertEqual(len(inst.cpus), len(inst.nodes))

    def test_set_node_list_pbs(self):
        """
        test different scenarios for setting node list
        """
        nodes = ['node1', 'node1', 'node2', 'node3']

        for key in ['pbs', 'slurm']:
            tmpdir = os.path.join(self.tmpdir, key)
            os.makedirs(tmpdir)
            if key == 'pbs':
                set_PBS_env(tmpdir, nodes=nodes)
            elif key == 'slurm':
                set_SLURM_env(tmpdir)

            pbs_class = SCHEDDICT[key]

            # normal run
            inst = getinstance(mpim.MPI, pbs_class, MympirunOption())
            inst.set_mpinodes()
            self.assertEqual(inst.mpinodes, nodes)

            # --double: start 2 processes for every entry in the nodefile
            inst.options.double = True
            inst.set_multiplier()
            inst.set_mpinodes()
            self.assertEqual(inst.mpinodes, nodes + nodes)

            # --multi: start n processes for every entry in the nodefile
            inst.options.double = False
            inst.options.multi = 3
            inst.set_multiplier()
            inst.set_mpinodes()
            self.assertEqual(inst.mpinodes, nodes + nodes + nodes)

            # --hybrid: start just n processes on every physical node
            inst.options.double = False
            inst.options.multi = None
            inst.options.hybrid = 1
            inst.set_multiplier()
            inst.set_mpinodes()
            self.assertEqual(inst.mpinodes, ['node1', 'node2', 'node3'])

    def test_get_local_sched(self):
        """ Test get_local_sched function """
        self.assertEqual(schedm.get_local_sched(SCHEDDICT.values()), Local)
        self.assertEqual(schedm.get_local_sched([]), None)
