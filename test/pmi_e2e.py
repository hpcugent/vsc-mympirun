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

import logging
logging.basicConfig(level=logging.DEBUG)

import os
import re

from pmi_utils import SLURM_2NODES, SLURM_2NODES_4GPUS, PMITest



class PMIEnd2End(PMITest):
    def test_simple(self):
        self.set_slurm_ompi4_ucx(SLURM_2NODES)

        self.pmirun(['--showmpi', '--debug'], pattern='Found MPI classes IntelMPI, OpenMPI4$')
        self.pmirun(['--showsched', '--debug'], pattern='Found Sched classes Slurm$')

    def test_ompi4_slurm(self):
        self.set_slurm_ompi4_ucx(SLURM_2NODES)

        # take into account that path may have characters like '(' and ')'
        cwd = re.escape(os.getcwd())
        pattern = '--chdir=' + cwd
        pattern += ' --nodes=2 --ntasks=64 --cpus-per-task=1 --mem-per-cpu=7600'
        pattern += ' --export=ALL --mpi=pmix_v3 --output=xyz --abc=123 --def=456'
        self.pmirun(['--debug', '--output=xyz', '--pass=abc=123,def=456', 'arg1', 'arg2'],
                    pattern=pattern+' arg1 arg2$')

    def test_ompi4_slurm_gpus(self):
        self.set_slurm_ompi4_ucx(SLURM_2NODES_4GPUS)

        # take into account that path may have characters like '(' and ')'
        cwd = re.escape(os.getcwd())
        pattern = '--chdir=' + cwd
        pattern += ' --nodes=2 --ntasks=8 --cpus-per-task=8 --mem-per-cpu=7600'
        pattern += ' --gpus-per-task=1'
        pattern += ' --export=ALL --mpi=pmix_v3'
        self.pmirun(['--debug', 'arg1', 'arg2'],
                    pattern=pattern+' arg1 arg2$')

        pattern = '--chdir=' + cwd
        pattern += ' --distribution=block:block:block'
        pattern += ' --nodes=2 --ntasks=8 --cpus-per-task=8 --mem-per-cpu=7600'
        pattern += ' --export=ALL --mpi=pmix_v3'
        self.pmirun(['--debug', '--all-gpus', '--distribute=pack', 'arg1', 'arg2'],
                    pattern=pattern+' arg1 arg2$')

    def test_print_launcher(self):
        self.set_slurm_ompi4_ucx(SLURM_2NODES)
        self.pmirun(['--print-launcher'], pattern=r'^srun.*--mpi=pmix_v3$')
