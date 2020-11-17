#
# Copyright 2011-2020 Ghent University
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
Intel MPI specific class

Documentation can be found at https://software.intel.com/en-us/node/528769
"""

import os
import socket
import tempfile
from vsc.utils.missing import nub
from vsc.utils.run import CmdList

from vsc.mympirun.common import version_in_range, which
from vsc.mympirun.mpi.mpi import MPI, RM_HYDRA_LAUNCHER

SCALABLE_PROGRESS_LOWER_THRESHOLD = 64


def _enable_disable(boolvalue):
    """Return enable/disable for boolean value"""
    return {True: 'enable', False: 'disable'}.get(bool(boolvalue))


def _one_zero(boolvalue):
    """Return enable/disable for boolean value"""
    return int(bool(boolvalue))


class IntelMPI(MPI):

    """An implementation of the MPI class for IntelMPI"""

    _mpiscriptname_for = ['impirun']
    _mpirun_for = 'impi'
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, None, '4.1.0.0'))

    RUNTIMEOPTION = {
        'options': {
            'mpdbulletproof': ("Start MPD in bulletproof", None, "store_true", False),
            'fallback': ("Enable device fallback", None, "store_true", False),
            'daplud': ("Enable DAPL UD connections", None, "store_true", False),
            'xrc': ("Enable Mellanox XRC", None, "store_true", False),
            },
        'prefix': 'impi',
        'description': ('Intel MPI options', 'Advanced options specific for Intel MPI'),
        }

    DEVICE_MPIDEVICE_MAP = {'ib': 'rdssm', 'det': 'det', 'shm': 'shm', 'socket': 'sock'}

    MPIRUN_LOCALHOSTNAME = socket.gethostname()

    OPTS_FROM_ENV_FLAVOR_PREFIX = ['I_MPI']

    OPTS_FROM_ENV_TEMPLATE = ['-envlist', '%(commaseparated)s']

    def _has_hydra(self):
        """Has HYDRA or not"""
        mgr = os.environ.get('I_MPI_PROCESS_MANAGER', None)
        if mgr == 'mpd':
            self.log.debug("No hydra, I_MPI_PROCESS_MANAGER set to %s", mgr)
            return False
        else:
            return super(IntelMPI, self)._has_hydra()

    def make_mpdboot_options(self):
        """
        Make the mpdboot options.
          - bulletproof customisation
        """
        super(IntelMPI, self).make_mpdboot_options()

        if self.options.impi_mpdbulletproof:
            # Start the mpd with the --bulletproof option
            mpd = which(['mpd.py'])
            self.mpdboot_options.append('-m "\\\"%s --bulletproof\\\""' % mpd)

    def set_impi_tmpdir(self):
        """Set location of temporary directory that Intel MPI should use."""
        # this one also needs to be set at runtime
        impi_tmpdir = tempfile.gettempdir()
        self.mpiexec_global_options['I_MPI_MPD_TMPDIR'] = impi_tmpdir
        os.environ['I_MPI_MPD_TMPDIR'] = impi_tmpdir
        self.log.debug("Set intel temp dir based on I_MPI_MPD_TMPDIR: %s", os.environ['I_MPI_MPD_TMPDIR'])

    def set_mpiexec_global_options(self):
        """Set mpiexec global options"""
        super(IntelMPI, self).set_mpiexec_global_options()

        self.set_impi_tmpdir()

        if self.options.debuglvl > 0:
            self.mpiexec_global_options['I_MPI_DEBUG'] = "+%s" % self.options.debuglvl
        if self.options.stats > 0:
            self.mpiexec_global_options['I_MPI_STATS'] = self.options.stats

        self.mpiexec_global_options['I_MPI_FALLBACK_DEVICE'] = _one_zero(self.options.impi_fallback)

        if self.device == 'det':
            self.mpiexec_global_options['I_MPI_DAT_LIBRARY'] = "libdatdet.so"
            self.mpiexec_global_options['I_MPI_DEVICE'] = 'default'
        else:
            self.mpiexec_global_options['I_MPI_DAT_LIBRARY'] = "libdat2.so"
            self.mpiexec_global_options['I_MPI_DEVICE'] = self.device

        if self.netmask:
            self.mpiexec_global_options['I_MPI_NETMASK'] = self.netmask

        self.mpiexec_global_options['I_MPI_PIN'] = _one_zero(self.options.pinmpi)

        if self.options.hybrid is not None and self.options.hybrid > 1:
            self.mpiexec_global_options["I_MPI_CPUINFO"] = "auto"

            if self.pinning_override_type in ('spread', 'scatter'):
                self.mpiexec_global_options["I_MPI_PIN_DOMAIN"] = "auto:scatter"
            else:
                self.mpiexec_global_options["I_MPI_PIN_DOMAIN"] = "auto:compact"

            # this only affects libiomp5 usage (ie intel compilers!)
            self.mpiexec_global_options["KMP_AFFINITY"] = "compact"

        if self.options.use_psm:
            if 'I_MPI_DEVICE' in self.mpiexec_global_options:
                del self.mpiexec_global_options['I_MPI_DEVICE']
            if 'TMI_CONFIG' in os.environ:
                tmicfg = os.environ.get('TMI_CONFIG')
                if not os.path.exists(tmicfg):
                    self.log.error('TMI_CONFIG set (%s), but not found.', tmicfg)
            elif not os.path.exists('/etc/tmi.conf'):
                self.log.debug("No TMI_CONFIG and no /etc/tmi.conf found, creating one")
                # make the psm tmi config
                tmicfg = os.path.join(self.mympirundir, '..', 'intelmpi.tmi.conf')
                if not os.path.exists(tmicfg):
                    open(tmicfg, 'w').write('psm 1.0 libtmip_psm.so " "\n')
                self.mpiexec_global_options['TMI_CONFIG'] = tmicfg
            self.mpiexec_global_options['I_MPI_FABRICS'] = 'shm:tmi'
            self.mpiexec_global_options['I_MPI_TMI_PROVIDER'] = 'psm'
            if self.options.debuglvl > 0:
                self.mpiexec_global_options['TMI_DEBUG'] = '1'

            if self.options.pinmpi:
                self.log.debug('Have PSM set affinity (disable I_MPI_PIN)')
                self.mpiexec_global_options['I_MPI_PIN'] = '0'

    def mpirun_prepare_execution(self):
        """Small change"""
        # intel mpi mpirun strips the --file option for mpdboot if it detects PBS_ENVIRONMENT to some fixed value
        # - we don't want that
        os.environ['PBS_ENVIRONMENT'] = 'PBS_BATCH_MPI'

        return super(IntelMPI, self).mpirun_prepare_execution()

    def pinning_override(self):
        """ pinning """

        self.log.debug("pinning_override: type %s ", self.pinning_override_type)

        cmd = CmdList()
        if self.pinning_override_type in ('packed', 'compact', 'bunch'):
            cmd.add(['-env', 'I_MPI_PIN_PROCESSOR_LIST=allcores:map=bunch'])
        elif self.pinning_override_type in ('spread', 'scatter'):
            cmd.add(['-env', 'I_MPI_PIN_PROCESSOR_LIST=allcores:map=%s' % self.pinning_override_type])
        else:
            self.log.raiseException("pinning_override: unsupported pinning_override_type  %s" %
                                    self.pinning_override_type)

        return cmd

    def make_machine_file(self, nodetxt=None, universe=None):
        """
        Make the machinefile.
        Parses the list of nodes that run an MPI process and writes this information to a machinefile.
        """
        if self.mpinodes is None:
            self.set_mpinodes()

        if nodetxt is None:
            nodetxt = ''
            if universe is not None and universe > 0:
                universe_ppn = self.get_universe_ncpus()
                for node in nub(self.mpinodes):
                    nodetxt += "%s:%s" % (node, universe_ppn[node])
                    if not self.has_hydra:
                        nodetxt += " ifhn=%s" % node
                    nodetxt += '\n'
            else:
                nodetxt = '\n'.join(self.mpinodes)

        super(IntelMPI, self).make_machine_file(nodetxt=nodetxt, universe=universe)


class IntelHydraMPI(IntelMPI):

    """An implementation of the MPI class for IntelMPI, with hydra """

    _mpiscriptname_for = ['ihmpirun']

    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '4.1.0.0', '5.0.3'))

    HYDRA = True
    HYDRA_LAUNCHER_NAME = "bootstrap"

    MPDBOOT_SET_INTERFACE = False

    DEVICE_MPIDEVICE_MAP = {
        'ib': 'shm:dapl',
        'det': 'det',
        'shm': 'shm',
        'socket': 'shm:tcp',
    }

    def set_mpiexec_global_options(self):
        """Set mpiexec global options"""
        super(IntelHydraMPI, self).set_mpiexec_global_options()
        self.mpiexec_global_options['I_MPI_FALLBACK'] = _enable_disable(self.options.impi_fallback)

        if 'I_MPI_DEVICE' in self.mpiexec_global_options:
            del self.mpiexec_global_options['I_MPI_DEVICE']
        if 'I_MPI_FABRICS' not in self.mpiexec_global_options:
            self.mpiexec_global_options['I_MPI_FABRICS'] = self.device

        scalable_progress = (self.multiplier * self.nodes_tot_cnt) > SCALABLE_PROGRESS_LOWER_THRESHOLD
        self.mpiexec_global_options['I_MPI_DAPL_SCALABLE_PROGRESS'] = _one_zero(scalable_progress)

        if self.options.impi_daplud:
            if self.options.impi_xrc:
                self.log.warning('Ignoring XRC setting when also requesting UD')
            self.mpiexec_global_options['I_MPI_DAPL_UD'] = _enable_disable(self.options.impi_daplud)
            if 'I_MPI_DAPL_UD_PROVIDER' not in os.environ:
                self.mpiexec_global_options['I_MPI_DAPL_UD_PROVIDER'] = 'ofa-v2-mlx4_0-1u'
        elif self.options.impi_xrc:
            # force it
            self.mpiexec_global_options['I_MPI_FABRICS'] = 'shm:ofa'
            self.mpiexec_global_options['I_MPI_OFA_USE_XRC'] = 1


class IntelHydraMPIPbsdsh(IntelHydraMPI):
    """ MPI class for IntelMPI, with hydra and supporting pbsdsh """
    # pbsdsh is supported from Intel MPI 5.0.3:
    # https://software.intel.com/sites/default/files/managed/b7/99/intelmpi-5.0-update3-releasenotes-linux.pdf
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '5.0.3', '2019.0'))

    HYDRA_LAUNCHER = RM_HYDRA_LAUNCHER


class IntelMPI2019(IntelHydraMPIPbsdsh):
    """MPI class for Intel MPI version 2019 and more recent."""

    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '2019.0', None))

    def set_impi_tmpdir(self):
        """Set location of temporary directory that Intel MPI should use."""
        # this one also needs to be set at runtime
        impi_tmpdir = tempfile.gettempdir()
        self.mpiexec_global_options['I_MPI_TMPDIR'] = impi_tmpdir
        os.environ['I_MPI_TMPDIR'] = impi_tmpdir
        self.log.debug("Specified temporary directory to use via $I_MPI_TMPDIR: %s", os.environ['I_MPI_TMPDIR'])

    def set_mpiexec_global_options(self):
        """Set mpiexec global options"""
        super(IntelMPI2019, self).set_mpiexec_global_options()

        # $I_MPI_CPUINFO is no longer valid for recent Intel MPI 2019 versions, so don't set it
        # (setting it anyway triggers a warning "I_MPI_CPUINFO environment variable is not supported")
        if 'I_MPI_CPUINFO' in self.mpiexec_global_options:
            del self.mpiexec_global_options['I_MPI_CPUINFO']
