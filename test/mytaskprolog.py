#
# Copyright 2019-2020 Ghent University
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

import os

import logging
logging.basicConfig(level=logging.DEBUG)

from pmi_utils import PMITest
from vsc.utils.affinity import sched_getaffinity, sched_setaffinity


class TaskPrologEnd2End(PMITest):
    def setUp(self):
        """Prepare to run test."""
        super(TaskPrologEnd2End, self).setUp()
        self.script = os.path.join(os.path.dirname(self.script), 'mytaskprolog.py')

    def test_simple(self):
        origaff = sched_getaffinity()

        aff = sched_getaffinity()
        aff.set_bits([1])  # only use first core (we can always assume there is one core

        sched_setaffinity(aff)
        self.pmirun([], pattern='export CUDA_VISIBLE_DEVICES=0')

        # restore
        sched_setaffinity(origaff)
