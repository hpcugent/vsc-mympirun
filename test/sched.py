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
Tests for the vsc.mympirun.mpi.sched module.

@author: Jeroen De Clerck
@author: Caroline De Brouwer
"""

import os
import shutil
import stat
import tempfile
import unittest

from vsc.mympirun.factory import getinstance
import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.option import MympirunOption
import vsc.mympirun.rm.sched as schedm
from vsc.mympirun.rm.local import Local
from vsc.mympirun.rm.pbs import PBS
from vsc.mympirun.rm.scoop import Scoop
from vsc.utils import fancylogger

SCHEDDICT = {
    "local": Local,
    "pbs": PBS, #doesn't work locally
    "scoop": Scoop,
    }

os.environ['PBS_JOBID'] = "1"
os.environ['PBS_NUM_PPN'] = "1"

def set_PBS_env():
    """ Set up the environment to recreate being in a hpc job """
    tmpdir = tempfile.mkdtemp()
    pbsnodefile = tempfile.NamedTemporaryFile(dir=tmpdir, delete=False)
    pbsnodefile.write("localhost\nlocalhost\n")
    pbsnodefile.close()
    os.environ['PBS_NODEFILE'] = pbsnodefile.name
    # make $PBS_NODEFILE and directory it is in read-only, just like in the real world
    os.chmod(pbsnodefile.name, stat.S_IRUSR)
    # make location directory where $PBS_NODEFILE resides read-only
    os.chmod(tmpdir, stat.S_IRUSR|stat.S_IXUSR)


def cleanup_PBS_env(orig_env):
    """ cleanup the mock job environment """
    # make $PBS_NODEFILE and the dir it is in writeable again after making it read-only in set_PBS_env
    os.chmod(os.environ['PBS_NODEFILE'], stat.S_IWUSR)
    os.chmod(os.path.dirname(os.environ['PBS_NODEFILE']), stat.S_IWUSR|stat.S_IRUSR|stat.S_IXUSR)
    shutil.rmtree(os.path.dirname(os.environ['PBS_NODEFILE']))
    os.environ = orig_env


class TestSched(unittest.TestCase):
    """tests for vsc.mympirun.mpi.sched functions"""

    def setUp(self):
        self.orig_environ = os.environ
        set_PBS_env()

    def tearDown(self):
        """Clean up after running test."""
        cleanup_PBS_env(self.orig_environ)

    def test_what_sched(self):
        """
        test if what_sched returns a corresponding scheduler"""
        for key, val in SCHEDDICT.iteritems():
            sched, found_sched = schedm.what_sched(key)
            print("key: %s, sched: %s, found_sched_: %s" % (key, sched, found_sched))
            self.assertEqual(sched, val)

    def test_get_id(self):
        """
        test if get_id correctly sets inst.sched_id

        get_id gets called by the __init__ of getinstance()
        """
        for _, val in SCHEDDICT.iteritems():
            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertTrue(inst.sched_id == os.environ.get(inst.SCHED_ENVIRON_ID, None) or
                            inst.sched_id.startswith("SCHED_%s" % inst.__class__.__name__))

    def test_core_on_this_node(self):
        """
        test if core_on_this_node() sets cores_per_node to an integer

        core_on_this_node() gets called by the __init__ of getinstance()
        """
        for _, val in SCHEDDICT.iteritems():
            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertTrue(isinstance(inst.cores_per_node, int))

    def test_which_cpus(self):
        """
        test if which_cpus() sets cpus to a list of unique integers

        which_cpus() gets called by the __init__ of getinstance()
        """
        for _, val in SCHEDDICT.iteritems():
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

    def test_set_node_list(self):
        """
        test different scenarios for setting node list
        """
        nodes = [
            'node1',
            'node1',
            'node2',
            'node3',
        ]
        pbs_class = SCHEDDICT['pbs']
        text = '\n'.join(nodes)
        os.chmod(os.environ['PBS_NODEFILE'], stat.S_IRUSR | stat.S_IWUSR)
        nodefile = open(os.environ['PBS_NODEFILE'], 'w')
        nodefile.seek(0)
        nodefile.write(text)
        nodefile.close()
        os.chmod(os.environ['PBS_NODEFILE'], stat.S_IRUSR)

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

