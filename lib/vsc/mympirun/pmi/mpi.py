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
Base PMI MPI class, all actual classes should inherit from this one

The role of the MPI class is very limited, mainly to provide supported PMI flavour/version
"""
from __future__ import print_function

from vsc.utils.fancylogger import getLogger
from vsc.mympirun.common import MpiKlass, eb_root_version, version_in_range
from vsc.mympirun.pmi.pmi import PMIxv3


class MPI(MpiKlass):

    PMI = None

    def __init__(self, options, cmdargs, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)

        self.options = options
        self.cmdargs = cmdargs

        super(MPI, self).__init__(**kwargs)

        # sanity checks
        if getattr(self, 'sched_id', None) is None:
            self.log.raiseException("__init__: sched_id is None (should be set by one of the Sched classes)")

        if not self.cmdargs:
            self.log.raiseException("__init__: no executable or command provided")

    def _modify_base_options(self, base_opts):
        """Hook to modify base options"""
        hybrid_help = ("Run in hybrid mode, specify number of processes per node. "
                       "When GPUs are present, the number of GPUs becomes the default.")
        base_opts['hybrid'] = tuple([hybrid_help] + list(base_opts['hybrid'][1:]))
        return base_opts

    def main(self):
        """Magic now!"""
        for name in ['tune', 'pmi', 'debug']:
            getattr(self, 'mpi_' + name)()

        pmicmd, run_function = self.pmicmd()

        cmd = pmicmd + self.cmdargs

        if self.options.dry_run:
            self.log.info("Dry run, only printing generated mpirun command...")
            print(' '.join(cmd))
            exitcode = 0
        else:
            exitcode, _ = run_function(cmd)

        if exitcode > 0:
            self.log.raiseException("main: exitcode %s > 0; cmd %s" % (exitcode, cmd))

    def has_ucx(self):
        """
        Determine if there is UCX support
        """
        root, version = eb_root_version('ucx')
        if root:
            self.log.debug("Found UCX root %s version %s", root, version)
            return True
        else:
            self.log.debug("No UCX root / version found")
            return False

    def has_pmi(self):
        """
        Determine if there is PMI support (and what versions/flavours)

        Return list with versions/flavours, or None in case of failure
        """
        if self.PMI is None:
            # TODO: detect somehow
            #   this is hard because most likely it will use the system pmi libraries
            self.log.error("Deteting PMI is not implemented")
            return None
        else:
            self.log.debug("Has pmi %s (forced)", self.PMI)
            return self.PMI

    def mpi_tune(self):
        """
        Tune MPI via environment variables.
        """
        if self.has_ucx():
            self.log.debug("UCX found, no tuning")
        else:
            # TODO: what is needed here?
            self.log.error("No tuning applied/supported")

    def mpi_pmi(self):
        """
        Set PMI via environment variables.
        """
        # e.g. for intel mpi, set IMPI variable pointing to pmi2 lib

    def mpi_debug(self):
        """
        Set MPI debug/stats via environment variables.
        """
        # e.g. for intel mpi, set IMPI variable pointing to pmi2 lib

    def _mpi_size(self, job_info):
        """
        Edit / adapt the current job_info to the requested mpi sizing
        """
        mpi_info = job_info.copy()

        hybrid = self.options.hybrid
        if hybrid is None:
            if mpi_info['ngpus'] is not None:
                hybrid = mpi_info['ngpus']
                self.log.debug("Setting number of GPUs %s as hybrid value", hybrid)

        if hybrid is not None:
            self.log.debug("Setting hybrid %s number of ranks", hybrid)
            mpi_info['nranks'] = self.options.hybrid

        return mpi_info


class OpenMPI4(MPI):

    """
    An implementation of the MPI class for OpenMPI supporting UCX and PMIx 3, starting with OpenMPI 4
    """

    _mpiscriptname_for = ['opmirun']
    _mpirun_for = 'OpenMPI'
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '4.0.0', None))

    PMI = [PMIxv3]


class Wurker(MPI):
    """
    Not an MPI class at all, to create the Slurm/srun wurker command
    """
    HIDDEN = True
