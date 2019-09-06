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
Slurm PMI class, i.e. wrap around srun
"""

from vsc.mympirun.pmi.sched import Sched
from vsc.utils.run import async_to_stdout


class Slurm(Sched):

    _sched_for = ['slurm']
    SCHED_ENVIRON_ID = 'SLURM_JOBID'
    SCHED_ENVIRON_NODE_INFO = 'SLURM_NODELIST'

    LAUNCHER = 'srun'

    def run_function(self):
        """
        srun supports redirection to file
        """
        args = []
        if self.options.output:
            args = ['--output', self.options.output]

        return async_to_stdout, args
