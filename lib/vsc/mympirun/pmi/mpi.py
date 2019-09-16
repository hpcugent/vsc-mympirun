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

import os

from vsc.utils.fancylogger import getLogger
from vsc.mympirun.common import MpiKlass, eb_root_version, version_in_range
from vsc.mympirun.pmi.pmi import PMIv2, PMIxv3


class MPI(MpiKlass):

    PMI = None
    # TODO: should be made generic somehow
    #   pmix3 pmi2 compat libraries might not work with all mpi apps
    #   but one can package the slurm pmi2 libs on different location
    #   ideally, one tests for pmix or not, and somehow tests that the pmi2 libs are not from pmix package
    PMI2LIBS = ['/usr/lib64/slurmpmi/libpmi2.so', '/usr/lib64/libpmi2.so']

    def __init__(self, options, cmdargs, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)

        self.options = options
        self.cmdargs = cmdargs

        super(MPI, self).__init__(**kwargs)

        self.ucx = self.has_ucx()
        self.hcoll = self.has_hcoll()

        # sanity checks
        if getattr(self, 'sched_id', None) is None:
            self.log.raiseException("__init__: sched_id is None (should be set by one of the Sched classes)")

        if not self.cmdargs:
            self.log.raiseException("__init__: no executable or command provided")

    def main(self):
        """Magic now!"""
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

    def has_hcoll(self):
        """
        Determine if there is hcoll / FCA support
        """
        root, version = eb_root_version('FCA')
        if root:
            self.log.debug("Found FCA/hcoll root %s version %s", root, version)
            return True
        else:
            self.log.debug("No FCA/hcoll root / version found")
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

    def _mpi_tune_hcoll_mpi(self):
        """MPI specific HCOLL tuning/enabling"""
        pass

    def _mpi_tune_mpi(self):
        """MPI specific tuning/enabling"""
        pass

    def _mpi_tune_ucx_mpi(self):
        """MPI specific UCX tuning/enabling"""
        pass

    def mpi_tune(self):
        """
        Tune MPI via environment variables.
        """
        self._mpi_tune_mpi()
        if self.ucx:
            self.log.debug("UCX found, no tuning")
            self._mpi_tune_ucx_mpi()

        if self.hcoll:
            # mpi hcoll settings
            self._mpi_tune_hcoll_mpi()

            # select device? autoselection?
            #self.set_env('HCOLL_MAIN_IB', 'mlx5_0:1')

            self.set_env('HCOLL_CUDA_SBGP', 'p2p')
            self.set_env('HCOLL_CUDA_BCOL', 'nccl')
        else:
            self.log.debug("No hcoll specific tuning since no hcoll")

    def _get_pmi2_lib(self):
        """Locate the pmi2 libs"""
        for lib in self.PMI2LIBS:
            if os.path.isfile(lib):
                return lib

        self.log.error("Cannot find PMIv2 lib from %s", self.PMI2LIBS)
        return None

    def mpi_pmi(self):
        """
        Set PMI via environment variables.
        """
        pass

    def _mpi_debug_mpi(self):
        """MPI specific debugging"""
        pass

    def _mpi_debug_ucx_mpi(self):
        """MPI specific UCX debugging"""
        pass

    def mpi_debug(self):
        """
        Set MPI debug/stats via environment variables.
        """
        # e.g. for intel mpi, set IMPI variable pointing to pmi2 lib
        self._mpi_debug_mpi()

        if self.options.debuglvl > 3:
            if self.ucx:
                self.set_env('UCX_LOG_LEVEL', 'debug')
                self._mpi_debug_ucx_mpi()

        if self.options.stats:
            if self.ucx:
                self.set_env('UCX_STATS_TRIGGER', 'exit')
                self.set_env('UCX_STATS_DEST', 'stdout')

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
            mpi_info['nranks'] = hybrid
            self.set_env('OMP_NUM_THREADS', mpi_info['ncores'] // hybrid)

        return mpi_info


class OpenMPI4(MPI):

    """
    An implementation of the MPI class for OpenMPI supporting UCX and PMIx 3, starting with OpenMPI 4
    """

    _mpiscriptname_for = ['opmirun']
    _mpirun_for = 'OpenMPI'
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '4.0.0', None))

    PMI = [PMIxv3]

    def ompi_env(self, what, key, value):
        """Set ompenmpi PMI variables"""
        self.set_env('OMPI_%s_%s' % (what.upper(), key), value)

    def _mpi_tune_hcoll_mpi(self):
        """hcoll enabling/tuning"""
        self.ompi_env('mca', 'coll_hcoll_enable', 1)
        self.ompi_env('mca', 'coll_hcoll_np', 0)

    def _mpi_tune_ucx_mpi(self):
        self.ompi_env('mca', 'pml', 'ucx')  # enable it. is also default?

    def _mpi_debug_mpi(self):
        """MPI specific debugging"""
        for mca in ['plm', 'pml', 'btl', 'mtl']:
            self.ompi_env('mca', '%s_base_verbose' % mca, self.options.debuglvl)

    def _mpi_debug_ucx_mpi(self):
        """MPI specific UCX debugging"""
        self.ompi_env('mca', 'pml_ucx_verbose', self.options.debuglvl)


class IntelMPI(MPI):
    """
    An implementation of the MPI class for IntelMPI supporting PMIv2
    """

    _mpiscriptname_for = ['ipmirun']
    _mpirun_for = 'impi'

    PMI = [PMIv2]

    def mpi_pmi(self):
        """
        Set PMI via environment variables.
        """
        pmi2lib = self._get_pmi2_lib()
        if pmi2lib is not None:
            self.set_env('I_MPI_PMI_LIBRARY', pmi2lib)

    def _mpi_debug_mpi(self):
        """MPI specific debugging"""
        if self.options.debuglvl > 0:
            self.set_env('I_MPI_DEBUG', "+%s" % self.options.debuglvl)
        if self.options.stats > 0:
            self.set_env('I_MPI_STATS', self.options.stats)


class Wurker(MPI):
    """
    Not an MPI class at all, to create the Slurm/srun wurker command
    """
    HIDDEN = True
