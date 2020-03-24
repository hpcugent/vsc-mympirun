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
wurker tests
"""

import logging
logging.basicConfig(level=logging.DEBUG)

import os
import re

from pmi_utils import SLURM_2NODES, PMITest


class TasksEnd2End(PMITest):
    def setUp(self):
        """Prepare to run test."""
        super(TasksEnd2End, self).setUp()
        self.script = os.path.join(os.path.dirname(self.script), 'mytasks.py')

    def test_ompi4_slurm(self):
        self.set_env(SLURM_2NODES)

        # take into account that path may have characters like '(' and ')'
        cwd = re.escape(os.getcwd())
        pattern = '--chdir=' + cwd
        pattern += ' --nodes=2 --ntasks=64 --cpus-per-task=1 --mem-per-cpu=7600'
        pattern += ' --export=ALL --mpi=none --output=xyz --abc=123 --def=456'
        self.pmirun(['--debug', '--output=xyz', '--pass=abc=123,def=456', 'arg1', 'arg2'],
                    pattern=pattern+' arg1 arg2$')
