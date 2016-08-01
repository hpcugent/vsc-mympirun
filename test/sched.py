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

import unittest

import vsc.mympirun.rm.sched as schedm
from vsc.mympirun.rm.local import Local
from vsc.mympirun.rm.pbs import PBS
from vsc.mympirun.rm.scoop import Scoop

class TestSched(unittest.TestCase):
    """tests for vsc.mympirun.mpi.sched functions"""

    def test_what_sched(self):
        """ test dingen"""
        schednames = {"local": Local, "pbs": PBS, "scoop": Scoop}
        for key, val in schednames.iteritems():
            sched, found_sched = schedm.what_sched(key)
            print("key: %s, sched: %s, found_sched_: %s" % (key, sched, found_sched))
            sched, found_sched = schedm.what_sched(key)
            self.assertEqual(sched, val)
