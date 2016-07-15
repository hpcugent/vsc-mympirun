#
# Copyright 2011-2016 Ghent University
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
import re

from distutils.version import LooseVersion
import socket
import tempfile

from vsc.mympirun.mpi.mpi import MPI, which

SCALABLE_PROGRESS_LOWER_THRESHOLD = 64


class IntelMPI(MPI):

    _mpiscriptname_for = ['impirun']
    _mpirun_for = ['impi']
    _mpirun_version = lambda x: LooseVersion(x) < LooseVersion("4.1.0.0")
    _mpirun_version = staticmethod(_mpirun_version)

    RUNTIMEOPTION = {'options': {'mpdbulletproof': ("Start MPD in bulletproof", None, "store_true", False),
                                 'fallback': ("Enable device fallback", None, "store_true", False),
                                 'daplud': ("Enable DAPL UD connections", None, "store_true", False),
                                 'xrc': ("Enable Mellanox XRC", None, "store_true", False),
                                 },
                     'prefix': 'impi',
                     'description': ('Intel MPI options', 'Advanced options specific for Intel MPI'),
                     }

    DEVICE_MPIDEVICE_MAP = {'ib': 'rdssm', 'det': 'det', 'shm': 'shm', 'socket': 'sock'}

    MPIRUN_LOCALHOSTNAME = socket.gethostname()

    PASS_VARIABLES_CLASS_PREFIX = ['I_MPI']

    MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION = "-envlist %(commaseparated)s"

    def _has_hydra(self):
        """Has HYDRA or not"""
        mgr = os.environ.get('I_MPI_PROCESS_MANAGER', None)
        if mgr == 'mpd':
            self.log.debug("No hydra, I_MPI_PROCESS_MANAGER set to %s", mgr)
            return False
        else:
            return super(IntelMPI, self)._has_hydra()

    def _pin_flavour(self, mp=None):
        if self.options.hybrid is not None and self.options.hybrid in (4,):
            mp = True
        self.log.debug("_pin_flavour: return %s", mp)
        return mp

    def get_universe_ncpus(self):
        """Return ppn for universe"""
        return self.nrnodes

    def get_pinning_override_variable(self):
        return 'PMI_RANK'

    def _enable_disable(self, boolvalue):
        """Return enable/disable for boolean value"""
        return {True: 'enable', False: 'disable'}.get(bool(boolvalue))

    def _one_zero(self, boolvalue):
        """Return enable/disable for boolean value"""
        return int(bool(boolvalue))

    def make_mpdboot_options(self):
        """
        Make the mpdboot options.
          - bulletproof customisation
        """
        super(IntelMPI, self).make_mpdboot_options()

        if self.options.impi_mpdbulletproof:
            """
            Start the mpd with the --bulletproof option
            """
            mpd = which(['mpd.py'])
            self.mpdboot_options.append('-m "\\\"%s --bulletproof\\\""' % mpd)

    def check_usable_cpus(self):
        """
        Check and act on fact of non-standard cpus (eg due to cpusets)
          - default: do nothing more then log
        """
        if not self.foundppn == len(self.cpus):
            # following works: taskset -c 1,3 mympirun --sched=local /usr/bin/env |grep I_MPI_PIN_INFO
            self.log.info("check_usable_cpus: non-standard cpus found: requested ppn %s, found cpus %s, usable cpus %s",
                          self.ppn, self.foundppn, len(self.cpus))

            if self.nruniquenodes > 1:
                self.log.info(("check_usable_cpus: more then one unique node requested. "
                               "Not setting I_MPI_PIN_PROCESSOR_LIST."))
            else:
                txt = ",".join(["%d" % x for x in self.cpus])
                self.mpiexec_global_options['I_MPI_PIN_PROCESSOR_LIST'] = txt
                os.environ['I_MPI_PIN_PROCESSOR_LIST'] = txt
                self.log.info("check_usable_cpus: one node requested. Setting I_MPI_PIN_PROCESSOR_LIST to %s", txt)

    def mpiexec_set_global_options(self):
        """Set mpiexec global options"""
        super(IntelMPI, self).mpiexec_set_global_options()

        # this one also needs to be set at runtime
        self.mpiexec_global_options['I_MPI_MPD_TMPDIR'] = tempfile.gettempdir()
        os.environ['I_MPI_MPD_TMPDIR'] = tempfile.gettempdir()
        self.log.debug("Set intel temp dir based on I_MPI_MPD_TMPDIR: %s", os.environ['I_MPI_MPD_TMPDIR'])

        if self.options.debuglvl > 0:
            self.mpiexec_global_options['I_MPI_DEBUG'] = "+%s" % self.options.debuglvl
        if self.options.stats > 0:
            self.mpiexec_global_options['I_MPI_STATS'] = self.options.stats

        self.mpiexec_global_options['I_MPI_FALLBACK_DEVICE'] = self._one_zero(self.options.impi_fallback)

        if self.device == 'det':
            self.mpiexec_global_options['I_MPI_DAT_LIBRARY'] = "libdatdet.so"
            self.mpiexec_global_options['I_MPI_DEVICE'] = 'default'
        else:
            self.mpiexec_global_options['I_MPI_DAT_LIBRARY'] = "libdat2.so"
            self.mpiexec_global_options['I_MPI_DEVICE'] = self.device

        if self.netmask:
            self.mpiexec_global_options['I_MPI_NETMASK'] = self.netmask

        self.mpiexec_global_options['I_MPI_PIN'] = self._one_zero(self.options.pinmpi)

        if self.options.hybrid is not None and self.options.hybrid > 1:
            self.mpiexec_global_options["I_MPI_CPUINFO"] = "auto"

            self.mpiexec_global_options["I_MPI_PIN_DOMAIN"] = "auto:compact"

            # this only affects libiomp5 usage (ie intel compilers!)
            self.mpiexec_global_options["KMP_AFFINITY"] = "compact"

            """
            if self.options.hybrid == 4:
                self.mpiexec_global_options["I_MPI_PIN_DOMAIN"]="cache"
            elif self.options.hybrid == 2:
                self.mpiexec_global_options["I_MPI_PIN_DOMAIN"]="socket"
            """

        if self.options.qlogic_ipath:
            if 'I_MPI_DEVICE' in self.mpiexec_global_options:
                del self.mpiexec_global_options['I_MPI_DEVICE']
            if 'TMI_CONFIG' in os.environ:
                tmicfg = os.environ.get('TMI_CONFIG')
                if not os.path.exists(tmicfg):
                    self.log.error('TMI_CONFIG set (%s), but not found.', tmicfg)
            elif not os.path.exists('/etc/tmi.conf'):
                self.log.debug("No TMI_CONFIG and no /etc/tmi.conf found, creating one")
                # make the psm tmi config
                tmicfg = os.path.join(self.mympirunbasedir, 'intelmpi.tmi.conf')
                if not os.path.exists(tmicfg):
                    open(tmicfg, 'w').write('psm 1.0 libtmip_psm.so " "\n')
                self.mpiexec_global_options['TMI_CONFIG'] = tmicfg
            self.mpiexec_global_options['I_MPI_FABRICS'] = 'shm:tmi'  # TODO shm:tmi or tmi
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


class IntelHydraMPI(IntelMPI):
    _mpiscriptname_for = ['ihmpirun']

    _mpirun_version = lambda x: LooseVersion(x) >= LooseVersion("4.1.0.0")
    _mpirun_version = staticmethod(_mpirun_version)

    HYDRA = True
    HYDRA_LAUNCHER_NAME = "bootstrap"

    MPDBOOT_SET_INTERFACE = False

    DEVICE_MPIDEVICE_MAP = {
        'ib': 'shm:dapl',
        'det': 'det',
        'shm': 'shm',
        'socket': 'shm:tcp',
    }

    def make_mpiexec_hydra_options(self):
        super(IntelMPI, self).make_mpiexec_hydra_options()
        self.mpiexec_options.append("-perhost %d" % self.mpiprocesspernode)

    def mpiexec_set_global_options(self):
        """Set mpiexec global options"""
        super(IntelHydraMPI, self).mpiexec_set_global_options()
        self.mpiexec_global_options['I_MPI_FALLBACK'] = self._enable_disable(self.options.impi_fallback)

        if 'I_MPI_DEVICE' in self.mpiexec_global_options:
            del self.mpiexec_global_options['I_MPI_DEVICE']
        if 'I_MPI_FABRICS' not in self.mpiexec_global_options:
            self.mpiexec_global_options['I_MPI_FABRICS'] = self.device

        scalable_progress = (self.mpiprocesspernode * self.nruniquenodes) > SCALABLE_PROGRESS_LOWER_THRESHOLD
        self.mpiexec_global_options['I_MPI_DAPL_SCALABLE_PROGRESS'] = self._one_zero(scalable_progress)

        if self.options.impi_daplud:
            if self.options.impi_xrc:
                self.log.warning('Ignoring XRC setting when also requesting UD')
            self.mpiexec_global_options['I_MPI_DAPL_UD'] = self._enable_disable(self.options.impi_daplud)
            if 'I_MPI_DAPL_UD_PROVIDER' not in os.environ:
                self.mpiexec_global_options['I_MPI_DAPL_UD_PROVIDER'] = 'ofa-v2-mlx4_0-1u'
        elif self.options.impi_xrc:
            # force it
            self.mpiexec_global_options['I_MPI_FABRICS'] = 'shm:ofa'
            self.mpiexec_global_options['I_MPI_OFA_USE_XRC'] = 1
