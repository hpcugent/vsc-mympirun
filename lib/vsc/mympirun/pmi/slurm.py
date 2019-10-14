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
        slurm_env = {}  # slurm enviroment

        dbg = []
        prefix = 'SLURM_'
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            dbg.append("%s=%s" % (key, value))
            # some basic type conversion
            try:
                value = int(value)
            except Exception as e:
                pass
            slurm_env[key[len(prefix):].lower()] = value

        dbgtxt = " ".join(sorted(dbg))
        # add sanity checks
        if [x for x in slurm_env.keys() if 'pack_group' in x]:
            # PACK_GROUP
            self.log.raiseException("This is an inhomogenous job: PACK_GROUP variables found: %s" % dbgtxt)
        if slurm_env['nnodes'] * slurm_env['cpus_on_node'] != slurm_env['nprocs']:
            self.log.raiseException("This is an inhomogenous job: nnodes*cpus_on_node!=nprocs: %s" % dbgtxt)
        else:
            self.log.debug("SLURM env variables %s", dbgtxt)

        job_info['tnodes'] = slurm_env['nnodes']
        job_info['ncores'] = slurm_env['cpus_on_node']

        job_info['nranks'] = slurm_env['ntasks'] // slurm_env['nnodes']  # probably not so relevant here
        if job_info['nranks'] * job_info['tnodes'] != slurm_env['ntasks']:
            self.log.raiseException("Total number of tasks is not equal ranks per node %s time number of nodes: %s" %
                                    (job_info['nranks'], dbgtxt))

        if 'mem_per_node' in slurm_env:
            job_info['nmem'] = slurm_env['mem_per_node']
        elif 'mem_per_cpu' in slurm_env:
            job_info['nmem'] = slurm_env['mem_per_cpu'] * slurm_env['cpus_on_node']
        else:
            self.log.debug("No memory specification found")

        if 'job_gpus' in slurm_env:
            try:
                # this should fail when slurm switched to compressed repr (eg 0-3 instead of current 0,1,2,3)
                ngpus = len(map(int, slurm_env['job_gpus'].split(',')))
                job_info['ngpus'] = ngpus
            except Exception as e:
                self.log.raiseException("Failed to get the number of gpus per node from %s: %s" %
                                        (slurm_env['job_gpus'], e))

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
        for key, value in os.environ.items():
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

        tn = mpi_info['tnodes']
        # all available nodes
        args.append("--nodes=%s" % tn)

        # 1 rank per task
        # tasks per node
        tpn = mpi_info['nranks']
        args.append("--ntasks=%s" % (tn * tpn))

        # cores per task
        cpt = mpi_info['ncores'] // tpn
        # sanity check
        if cpt * tpn != mpi_info['ncores']:
            self.log.raiseException("Imbalanced tasks per node %s vs cores per node %s; using %s cores per task" %
                                    (tpn, mpi_info['ncores'], cpt))

        args.append("--cpus-per-task=%s" % cpt)

        # redistribute all the memory to the tasks/cores
        if mpi_info['nmem'] is None:
            self.log.debug("No nmem specified found (assuming slurm.conf defaults)")
        else:
            args.append("--mem-per-cpu=%s" % (mpi_info['nmem'] // mpi_info['ncores']))

        if mpi_info['ngpus'] is not None:
            # gpus per task
            gpt = mpi_info['ngpus'] // tpn
            # sanity check
            if gpt * tpn != mpi_info['ngpus']:
                self.log.raiseException("Imbalanced tasks per node %s vs gpus per node %s; using %s gpus per task" %
                                        (tpn, mpi_info['ngpus'], gpt))
            if self.options.all_gpus:
                # TODO: this is not slurm specific, needs to be factored out
                self.log.debug("Not limiting gpus to %s per task, gpus-all set", gpt)
            else:
                args.append("--gpus-per-task=%s" % gpt)

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
