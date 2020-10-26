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
Base PMI MPI class, all actual classes should inherit from this one

The role of the MPI class is very limited, mainly to provide supported PMI flavour/version
"""
from __future__ import print_function

import os
import re

from vsc.utils.fancylogger import getLogger
from vsc.utils.run import run
from vsc.mympirun.common import MpiBase, eb_root_version, version_in_range
from vsc.mympirun.pmi.pmi import PMIv2, PMIxv3

# TODO: should be made generic somehow
#   pmix3 pmi2 compat libraries might not work with all mpi apps
#   but one can package the slurm pmi2 libs on different location
#   ideally, one tests for pmix or not, and somehow tests that the pmi2 libs are not from pmix package
AUTOMATIC_LIB = 'AUTOMATIC'
SLURM_PMI1_LIB = 'SLURM1'
SLURM_PMI2_LIB = 'SLURM2'
SYSTEM_PMI1_LIB = 'SYSTEM1'
SYSTEM_PMI2_LIB = 'SYSTEM2'

PMI2LIBS = {
    AUTOMATIC_LIB: '/automatic/via/does/not/exist',  # non-exisiting file picks up some defaults and "stuff works"
    SLURM_PMI1_LIB: '/usr/lib64/slurmpmi/libpmi.so',
    SLURM_PMI2_LIB: '/usr/lib64/slurmpmi/libpmi2.so',
    SYSTEM_PMI1_LIB: '/usr/lib64/libpmi.so',  # possibly/likely pmix
    SYSTEM_PMI2_LIB: '/usr/lib64/libpmi2.so',  # possibly/likely pmix
}


class MPI(MpiBase):

    PMI = None

    def __init__(self, options, cmdargs, **kwargs):
        """Initialise, named attributes are passed to parent MpiBase class"""
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)

        self.options = options
        self.cmdargs = cmdargs

        super(MPI, self).__init__(**kwargs)

        self.ucx = self.has_ucx()
        self.hcoll = self.has_hcoll()

        # sanity checks
        if not self.cmdargs and not self.options.print_launcher:
            self.log.raiseException("__init__: no executable or command provided")

    def main(self):
        """
        Main method that actually runs the launcher:
        build the pmi command using pmicd method and add the original command arguments
        """
        pmicmd, run_function = self.pmicmd()

        cmd = pmicmd + self.cmdargs

        if self.options.print_launcher:
            print(' '.join(pmicmd))
            exitcode = 0
        elif self.options.dry_run:
            self.log.info("Dry run, only printing generated mpirun command...")
            print(' '.join(cmd))
            exitcode = 0
        else:
            exitcode, _ = run_function(cmd)

        if exitcode > 0:
            self.log.raiseException("main: exitcode %s > 0; cmd %s" % (exitcode, cmd))

    def _eb_has(self, name, txt=None):
        """Determine is the is a EB module loaded for name"""
        if txt is None:
            txt = name

        root, version = eb_root_version(name)
        if root:
            self.log.debug("Found %s root %s version %s", txt, root, version)
            return True
        else:
            self.log.debug("No %s root / version found", txt)
            return False

    def has_ucx(self):
        """
        Determine if there is UCX support
        """
        return self._eb_has('UCX')

    def has_hcoll(self):
        """
        Determine if there is hcoll / FCA support
        """
        return self._eb_has('FCA', txt='hcoll / FCA')

    def has_pmi(self):
        """
        Determine if there is PMI support (and what versions/flavours)

        Return list with versions/flavours, or None in case of failure
        """
        if self.PMI is None:
            # TODO: detect somehow
            #   this is hard because most likely it will use the system pmi libraries
            self.log.error("Detecting PMI is not implemented")
            return None
        else:
            self.log.debug("Has PMI %s (forced)", self.PMI)
            return self.PMI

    def mpi_tune_hcoll_mpi(self):
        """MPI specific HCOLL tuning/enabling"""
        self.log.debug("No MPI-specific hcoll tuning")

    def mpi_tune_mpi(self):
        """MPI specific tuning/enabling"""
        self.log.debug("No MPI-specific MPI tuning")

    def mpi_tune_ucx_mpi(self):
        """MPI specific UCX tuning/enabling"""
        self.log.debug("No MPI-specific UCX tuning")

    def mpi_tune(self):
        """
        Tune MPI via environment variables.
        """
        self.mpi_tune_mpi()

        if self.ucx:
            # TODO: tag matching: UCX_RC_VERBS_TM_ENABLE=y ?
            self.mpi_tune_ucx_mpi()
        else:
            self.log.debug("No UCX found, so no UCX tuning")

        if self.hcoll:
            # mpi hcoll settings
            # see Mellanox Fabric Collective Accelerator documentation of the HPC-X toolkit
            self.mpi_tune_hcoll_mpi()

            # TODO: test this actually works: select device? autoselection?
            #self.set_env('HCOLL_MAIN_IB', 'mlx5_0:1')

            # enable CUDA collectives via NCCL
            self.set_env('HCOLL_CUDA_SBGP', 'p2p', keep=True)
            self.set_env('HCOLL_CUDA_BCOL', 'nccl', keep=True)
        else:
            self.log.debug("No hcoll found, no hcoll tuning")

    def get_pmi2_lib(self, pref=None):
        """Locate the pmi2 libs"""
        if pref is None:
            pref = sorted(PMI2LIBS.keys())
            # move auto last, it will always be "found"
            pref.remove(AUTOMATIC_LIB)
            pref.append(AUTOMATIC_LIB)

        for name in pref:
            lib = PMI2LIBS[name]
            if name == AUTOMATIC_LIB:
                self.log.debug("Using %s nonexisting PMIv2 lib %s from %s (%s)", AUTOMATIC_LIB, lib, pref, PMI2LIBS)
                return lib
            elif os.path.isfile(lib):
                self.log.debug("Found PMIv2 lib %s from %s (%s)", lib, pref, PMI2LIBS)
                return lib

        self.log.error("Cannot find PMIv2 lib from %s (%s)", pref, PMI2LIBS)
        return None

    def mpi_pmi(self):
        """
        Enable PMI e.g. via environment variables.
        """
        self.log.debug("Nothing to do to enable PMI")

    def mpi_debug_mpi(self):
        """MPI specific debugging"""
        self.log.debug("No MPI debugging")

    def mpi_debug_ucx_mpi(self):
        """MPI specific UCX debugging"""
        self.log.debug("No MPI-speciifc UCX debugging")

    def mpi_debug(self):
        """
        Set MPI debug/stats via environment variables.
        """
        # e.g. for intel mpi, set IMPI variable pointing to pmi2 lib
        self.mpi_debug_mpi()

        if self.options.debuglvl > 3:
            if self.ucx:
                self.set_env('UCX_LOG_LEVEL', 'debug')
                self.mpi_debug_ucx_mpi()

        if self.options.stats:
            if self.ucx:
                # report UCX stats at the end to stdout
                self.set_env('UCX_STATS_TRIGGER', 'exit')
                self.set_env('UCX_STATS_DEST', 'stdout')

    def mpi_size(self, job_info):
        """
        Edit / adapt the current job_info to the requested mpi sizing
        """
        mpi_info = job_info.deepcopy()

        hybrid = self.options.hybrid
        if hybrid is None:
            if mpi_info.gpus is not None:
                hybrid = mpi_info.gpus
                self.log.debug("Setting number of GPUs %s as hybrid value", hybrid)

        if hybrid is not None:
            self.log.debug("Setting hybrid %s number of ranks", hybrid)
            mpi_info.ranks = hybrid
            self.set_env('OMP_NUM_THREADS', max(1, mpi_info.cores // hybrid))

        return mpi_info


class OpenMPI31xOr4x(MPI):
    """
    An implementation of the MPI class for OpenMPI 3.1.x + OpenMPI 4.x (and more recent), supporting PMIx 3.x
    """
    _mpiscriptname_for = ['opmirun']
    _mpirun_for = 'OpenMPI'
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '3.1.0', None))

    PMI = [PMIxv3]

    def has_ucx(self):
        """Determine whether or not to use the UCX Point-to-Point Messaging Layer (PML)."""
        # only use UCX as PML if ompi_info reports it as supported *and* a UCX module is loaded (don't use system UCX)

        # use UCX if 'ompi_info' reports that it is a supported PML;
        cmd = "ompi_info"
        ec, out = run(cmd)
        if ec:
            self.log.raiseException("has_ucx: failed to run cmd '%s', ec: %s, out: %s" % (cmd, ec, out))

        ompi_info_pml_ucx = bool(re.search(' pml: ucx ', out))

        return ompi_info_pml_ucx and self._eb_has('UCX')

    def ompi_env(self, what, key, value):
        """Set environment variables for OpenMPI"""
        self.set_env('OMPI_%s_%s' % (what.upper(), key), value)

    def mpi_tune_hcoll_mpi(self):
        """hcoll enabling/tuning"""
        self.ompi_env('mca', 'coll_hcoll_enable', 1)
        # use HCOLL for all communications with more than (np=) 0 tasks
        self.ompi_env('mca', 'coll_hcoll_np', 0)

    def mpi_tune_ucx_mpi(self):
        """MPI-specific UCX tuning"""
        # use UCX as point-to-point management layer
        self.ompi_env('mca', 'pml', 'ucx')
        # disable uct btl, see http://openucx.github.io/ucx/running.html
        self.ompi_env('mca', 'btl', '^uct')

    def mpi_debug_mpi(self):
        """MPI specific debugging"""
        # set debug level for plm (Process Lifecycle Management), pml (Point-to-point Messaging Layer),
        #  btl (Byte Transfer Layer) and mtl (Matching Transport Layer)
        for mca in ['plm', 'pml', 'btl', 'mtl']:
            self.ompi_env('mca', '%s_base_verbose' % mca, self.options.debuglvl)

    def mpi_debug_ucx_mpi(self):
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
        # possibly add option to select the pmi2 backend module
        #    - intel mpi guide also mentions that dapl tuning is required
        pmi2lib = self.get_pmi2_lib([SLURM_PMI1_LIB, SYSTEM_PMI1_LIB, AUTOMATIC_LIB])
        if pmi2lib is not None:
            self.set_env('I_MPI_PMI_LIBRARY', pmi2lib)

    def mpi_debug_mpi(self):
        """MPI specific debugging"""
        if self.options.debuglvl > 0:
            # use '+' for rank#pid@hostname prefix in the messages
            self.set_env('I_MPI_DEBUG', "+%s" % self.options.debuglvl)
        if self.options.stats > 0:
            self.set_env('I_MPI_STATS', self.options.stats)


class Tasks(MPI):
    """
    Not an MPI class at all, to create the Slurm/srun mytasks command
    """
    # hide it from showmpi option output
    HIDDEN = True
