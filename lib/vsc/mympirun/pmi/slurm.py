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

import os
import re

from vsc.mympirun.pmi.sched import Sched
from vsc.mympirun.pmi.pmi import PMIX
from vsc.utils.run import async_to_stdout

class Slurm(Sched):

    _sched_for = ['slurm']
    SCHED_ENVIRON_ID = 'SLURM_JOB_ID'

    LAUNCHER = 'srun'

    def run_function(self):
        """
        srun itself supports redirection to file
        """
        args = []
        if self.options.output:
            args = ['--output=%s' % self.options.output]

        return async_to_stdout, args

    def pmicmd_sched(self):
        """Generate the sched related arguments to the launcher as a list"""
        args = []

        # sbatch will set the sbatch parameters as environment variables and they will get picked up by srun
        args.append("--chdir=" + os.getcwd())

        return args

    def pmicmd_environment(self):
        """export everything"""
        return ['--export=ALL']

    def pmicmd_mpi(self):
        """Handle PMI to --mpi"""
        for pmi in self.PMI:
            flavour = None
            if pmi.FLAVOUR == PMIX:
                flavour = 'pmix'
                if pmi.VERSION == 3:
                    flavour += '_v3'
                else:
                    self.log.warn("Unsupported PMIx version %s" % pmi)
            else:
                self.log.error("Unsupported PMI %s" % pmi)

            if flavour is not None:
                # first one wins
                self.log.debug("Mapped PMI %s to flavour %s", pmi, flavour)
                return ["--mpi=%s" % flavour]

        self.log.error("No supported PMIs")
        return []

    def _job_info(self, job_info):
        """
        Fill in/complete/edit job_info dict and return it

        # relevant variables to use
        SLURM_CPUS_ON_NODE=32
        SLURM_JOB_CPUS_PER_NODE=32(x2)
        SLURM_JOB_GPUS=0,1,2,3
        SLURM_JOB_NODELIST=node[3302-3303]
        SLURM_JOB_NUM_NODES=2
        SLURM_MEM_PER_CPU=7600
        SLURM_NNODES=2
        SLURM_NPROCS=64
        SLURM_NTASKS=64
        """
        se = {}  # slurm enviroment

        # TODO: check here if the requested gpus are usable or not (eg corresponding CUDA_DEVICES)

        dbg = []
        prefix = 'SLURM_'
        for k, v in os.environ.items():
            if not k.startswith(prefix):
                continue
            dbg.append("%s=%s" % (k, v))
            # some basic type conversion
            try:
                v = int(v)
            except Exception as e:
                pass
            se[k[len(prefix):].lower()] = v

        dbgtxt = " ".join(sorted(dbg))
        # add sanity checks
        if [x for x in se.keys() if 'pack_group' in x]:
            # PACK_GROUP
            self.log.error("This is an inhomogenous job: PACK_GROUP variables found: %s", dbgtxt)
        if se['nnodes'] * se['cpus_on_node'] != se['nprocs']:
            self.log.error("This is an inhomogenous job: nnodes*cpus_on_node!=nprocs: %s", dbgtxt)
        else:
            self.log.debug("SLURM env variables %s", dbgtxt)

        job_info['tnodes'] = se['nnodes']
        job_info['ncores'] = se['cpus_on_node']

        job_info['nranks'] = int(se['ntasks'] / se['nnodes'])  # probably not so relevant here
        if job_info['nranks'] * job_info['tnodes'] != se['ntasks']:
            self.log.error("Total number of tasks is not equal ranks per node %s time number of nodes: %s",
                           job_info['nranks'], dbgtxt)

        if 'mem_per_node' in se:
            job_info['nmem'] = se['mem_per_node']
        elif 'mem_per_cpu' in se:
            job_info['nmem'] = se['mem_per_cpu'] * se['cpus_on_node']
        else:
            self.log.error

        if 'job_gpus' in se:
            try:
                # this should fail when slurm switched to compressed repr (eg 0-3 instead of current 0,1,2,3)
                ngpus = len(map(int, se['job_gpus'].split(',')))
                job_info['ngpus'] = ngpus
            except Exception as e:
                self.log.error("Failed to get the number of gpus per node from %s: %s", se['job_gpus'], e)

        return job_info

    def _pmicmd_size_args(self, mpi_info):
        """
        Convert mpi_info into launcher list of args
        """

        # patterns to cleanup
        cleanup = ['MEM', 'CPU', 'GPU', 'TASK']
        cleanupre = re.compile(r'^SLURM.*(' + '|'.join(cleanup) + ').*')

        removed = []
        for k, v in os.environ.items():
            if cleanupre.search(k):
                removed.append("%s=%s" % (k, v))
                del os.environ[k]

        if removed:
            self.log.debug("Unset environment variables %s", " ".join(removed))
        else:
            self.log.debug("No environment variables unset")

        # 1 task per core?
        # specify --cpus-per-task and not --ntasks and  --ntasks-per-node=?

        # redistribute all the memory to the tasks/cores

        return []

    def pmicmd_debug(self):
        """Debug related args/options"""
        # TODO --cpu-bind=verbose --mem-bind=verbose
        return []


class Wurker(Sched):
    HIDDEN = True
