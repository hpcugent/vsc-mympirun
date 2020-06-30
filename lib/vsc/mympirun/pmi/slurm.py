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
Slurm PMI class, i.e. wrap around srun
"""

import os
import re

from vsc.mympirun.pmi.sched import Sched
from vsc.mympirun.pmi.pmi import PMI, PMIX
from vsc.utils.run import async_to_stdout
from vsc.mympirun.pmi.option import DISTRIBUTE_PACK, DISTRIBUTE_CYCLE


DISTRIBUTE_MAP = {
    DISTRIBUTE_PACK: 'block:block:block',
    DISTRIBUTE_CYCLE: 'cycle:cycle:cycle',
}


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

        # run from current directory
        #   sbatch will set the sbatch parameters as environment variables and they will get picked up by srun
        args.append("--chdir=" + os.getcwd())

        if self.options.distribute:
            args.append("--distribution=%s" % DISTRIBUTE_MAP[self.options.distribute])

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
                    self.log.warn("Unsupported PMIx version %s, trying with generic %s", pmi, flavour)
            elif pmi.FLAVOUR == PMI:
                if pmi.VERSION == 2:
                    flavour = 'pmi2'
                else:
                    self.log.raiseException("Unsupported PMI version %s" % pmi)
            else:
                self.log.raiseException("Unsupported PMI %s" % pmi)

            if flavour is not None:
                # first one wins
                self.log.debug("Mapped PMI %s to flavour %s", pmi, flavour)
                return ["--mpi=%s" % flavour]

        self.log.raiseException("No supported PMIs")
        return []

    def job_info(self, job_info):
        """
        Fill in/complete/edit job_info and return it
        Relevant variables to use
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
        dbgtxt = ', '.join(['%s=%s' % (k, v) for k, v in sorted(os.environ.items()) if k.startswith('SLURM_')])

        if 'SLURM_PACK_SIZE' in os.environ:
            self.log.raiseException("This is an inhomogenous job (PACK_SIZE set): %s" % dbgtxt)

        nodes = int(os.environ['SLURM_NNODES'])
        cores = int(os.environ['SLURM_CPUS_ON_NODE'])
        job_info.nodes = nodes
        job_info.cores = cores

        # add sanity checks
        if nodes * cores != int(os.environ['SLURM_NPROCS']):
            self.log.raiseException("This is an inhomogenous job: nodes*cores!=nprocs: %s" % dbgtxt)
        else:
            self.log.debug("SLURM env variables %s", dbgtxt)

        total_tasks = int(os.environ['SLURM_NTASKS'])

        job_info.ranks = total_tasks // nodes
        if total_tasks % nodes:
            self.log.raiseException("Total number of tasks is not equal ranks per node %s time number of nodes: %s" %
                                    (job_info.ranks, dbgtxt))

        mem = os.environ.get('SLURM_MEM_PER_NODE', int(os.environ.get('SLURM_MEM_PER_CPU', -1)) * cores)
        if mem < 0:
            self.log.debug("No memory specification found")
        else:
            job_info.mem = int(mem)

        if 'SLURM_JOB_GPUS' in os.environ:
            try:
                # this should fail when slurm switched to compressed repr (eg 0-3 instead of current 0,1,2,3)
                ngpus = len(list(map(int, os.environ['SLURM_JOB_GPUS'].split(','))))
            except Exception as e:
                self.log.raiseException("Failed to get the number of gpus per node from %s: %s" % (dbgtxt, e))

            job_info.gpus = ngpus

        return job_info

    def pmicmd_size_args(self, mpi_info):
        """
        Convert mpi_info into launcher list of args
        """

        # patterns to cleanup
        cleanup = ['MEM', 'CPU', 'GPU', 'TASK', 'NODE', 'PROC']
        cleanupre = re.compile(r'^SLURM_.*(' + '|'.join(cleanup) + ').*')
        # whitelist, precedes cleanup
        keep = ['NODELIST']
        keepre = re.compile(r'^SLURM_.*(' + '|'.join(keep) + ').*')

        removed = []
        for key, value in sorted(os.environ.items()):
            if keepre.search(key):
                continue
            elif cleanupre.search(key):
                removed.append("%s=%s" % (key, value))
                del os.environ[key]

        if removed:
            self.log.debug("Unset environment variables %s", " ".join(removed))
        else:
            self.log.debug("No environment variables unset")

        args = []

        # all available nodes
        args.append("--nodes=%s" % mpi_info.nodes)

        # 1 rank per task
        args.append("--ntasks=%s" % (mpi_info.nodes * mpi_info.ranks))

        # sanity check
        if mpi_info.cores % mpi_info.ranks:
            self.log.raiseException("Imbalanced cores and ranks per node %s" % mpi_info)
        else:
            # cores per task == cores per rank
            args.append("--cpus-per-task=%s" % (mpi_info.cores // mpi_info.ranks))


        # redistribute all the memory to the tasks/cores
        if mpi_info.mem is None:
            self.log.debug("No memory specified (assuming slurm.conf defaults)")
        else:
            args.append("--mem-per-cpu=%s" % (mpi_info.mem // mpi_info.cores))

        if mpi_info.gpus is not None:
            if self.options.all_gpus:
                # TODO: this is not slurm specific, needs to be factored out
                self.log.debug("Not limiting gpus per rank, gpus-all set")
            elif mpi_info.gpus < mpi_info.ranks:
                # enable MPS
                #   probably also needs to check for imbalance
                self.log.raiseException("MPS not supported yet: %s" % mpi_info)
            elif mpi_info.gpus % mpi_info.ranks:
                self.log.raiseException("Imbalanced tasks and gpus per node (ranks < gpus): %s" % mpi_info)
            else:
                args.append("--gpus-per-task=%s" % (mpi_info.gpus // mpi_info.ranks))

        return args

    def pmicmd_debug(self):
        """Debug related args/options for launcher"""
        args = ['--verbose'] * self.options.debuglvl

        if self.options.debuglvl > 0:
            args.append('--cpu-bind=verbose')
            args.append('--mem-bind=verbose')
            args.append('--accel-bind=v')

            if self.options.debuglvl > 3:
                dbg = 'verbose'
            else:
                dbg = 'info'
            args.append('--slurmd-debug=%s' % dbg)

        return args


class Tasks(Slurm):
    """Non-mpi srun workload"""
    HIDDEN = True

    def pmicmd_mpi(self):
        """Disable mpi"""
        self.log.debug("No mpi in mytasks")
        return ["--mpi=none"]
