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
Tests for the vsc.mympirun.mpi.sched module.

@author: Jeroen De Clerck
"""

import os
import unittest

from vsc.mympirun.factory import getinstance
import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.option import MympirunOption
import vsc.mympirun.rm.sched as schedm
from vsc.mympirun.rm.local import Local
from vsc.mympirun.rm.pbs import PBS
from vsc.mympirun.rm.scoop import Scoop
from vsc.utils.affinity import sched_getaffinity

SCHEDDICT = {
    "local": Local,
    #"pbs": PBS, #doesn't work locally
    "scoop": Scoop,
    }


class TestSched(unittest.TestCase):
    """tests for vsc.mympirun.mpi.sched functions"""

    def test_what_sched(self):
        """
        test if what_sched returns a corresponding scheduler"""
        for key, val in SCHEDDICT.iteritems():
            sched, found_sched = schedm.what_sched(key)
            print("key: %s, sched: %s, found_sched_: %s" % (key, sched, found_sched))
            sched, found_sched = schedm.what_sched(key)
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
        test if core_on_this_node() sets foundppn to an integer

        core_on_this_node() gets called by the __init__ of getinstance()
        """
        for _, val in SCHEDDICT.iteritems():
            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertTrue(isinstance(inst.foundppn, int))

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
        self.assertEqual(len(inst.cpus), inst.nrnodes)

    def test_get_unique_nodes(self):
        """
        test if get_unique_nodes() sets uniquenodes to the unique elements of nodes

        get_unique_nodes() gets called by the __init__ of getinstance()
        """
        for _, val in SCHEDDICT.iteritems():
            inst = getinstance(mpim.MPI, val, MympirunOption())
            self.assertEqual(set(inst.uniquenodes), set(inst.nodes))
            self.assertEqual(inst.nruniquenodes, len(set(inst.nodes)))
