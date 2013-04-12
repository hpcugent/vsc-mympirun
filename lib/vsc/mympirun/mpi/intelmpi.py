#
# Copyright 2011-2012 Ghent University
# Copyright 2011-2012 Stijn De Weirdt
#
# This file is part of VSC-tools,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/VSC-tools
#
# VSC-tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# VSC-tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VSC-tools. If not, see <http://www.gnu.org/licenses/>.
#

"""
Intel MPI specific class
"""

from distutils.version import LooseVersion
from vsc.mympirun.mpi.mpi import MPI, which
import os, re
import socket

class IntelMPI(MPI):
    """TODO: support for tuning
        - runtune: generate the tuning files
        - tuneconf: pass the generated config files
    """

    _mpiscriptname_for = ['impirun']
    _mpirun_for = ['impi']
    _mpirun_version = lambda x: LooseVersion(x) < LooseVersion("4.1.0.0")
    _mpirun_version = staticmethod(_mpirun_version)

    RUNTIMEOPTION = {'options':{'mpdbulletproof':("Start MPD in bulletproof", None, "store_true", False),
                                'fallback':("Enable device fallback", None, "store_true", False),
                                'daplud':("Enable DAPL UD connections", None, "store_true", False),
                                },
                     'prefix':'impi',
                     'description': ('Intel MPI options', 'Advanced options specific for Intel MPI'),
                     }


    DEVICE_MPIDEVICE_MAP = {
                            'ib':'rdssm',
                            'det':'det',
                            'shm':'shm',
                            'socket':'shm:sock',
                            }

    MPIRUN_LOCALHOSTNAME = socket.gethostname()

    PASS_VARIABLES_CLASS_PREFIX = ['I_MPI']

    MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION = "-envlist %(commaseparated)s"

    def _pin_flavour(self, mp=None):
        if self.options.hybrid is not None and self.options.hybrid in (4,):
            mp = True
        self.log.debug("_pin_flavour: return %s" % mp)
        return mp

    def get_universe_ncpus(self):
        """Return ppn for universe"""
        return self.nrnodes

    def get_pinning_override_variable(self):
        return 'PMI_RANK'

    def _enable_disable(self, boolvalue):
        """Return enable/disable for boolean value"""
        return {True:'enable', False:'disable'}.get(bool(boolvalue))

    def _one_zero(self, boolvalue):
        """Return enable/disable for boolean value"""
        return int(bool(boolvalue))

    def make_mpdboot_options(self):
        """Make the mpdboot options.
            bulletproof customisation
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
            self.log.info(("check_usable_cpus: non-standard cpus found: "
                           "requested ppn %s, found cpus %s, usable cpus %s") %
                          (self.ppn, self.foundppn, len(self.cpus)))

            if self.nruniquenodes > 1:
                self.log.info(("check_usable_cpus: more then one unique node requested. "
                               "Not setting I_MPI_PIN_PROCESSOR_LIST."))
            else:
                txt = ",".join(["%d" % x for x in self.cpus])
                self.mpiexec_global_options['I_MPI_PIN_PROCESSOR_LIST'] = txt
                self._setenv('I_MPI_PIN_PROCESSOR_LIST', txt)
                self.log.info(("check_usable_cpus: one node requested. "
                               "Setting I_MPI_PIN_PROCESSOR_LIST to %s") % txt)

    def mpiexec_set_global_options(self):
        """Set mpiexec global options"""
        super(IntelMPI, self).mpiexec_set_global_options()

        # this one also needs to be set at runtime
        self.mpiexec_global_options['I_MPI_MPD_TMPDIR'] = "/tmp"
        self._setenv('I_MPI_MPD_TMPDIR', "/tmp")

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

        self.mpiexec_global_options['I_MPI_FALLBACK_DEVICE'] = self._one_zero(self.options.pinmpi)

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
            self.mpiexec_global_options['I_MPI_FABRICS'] = 'shm:tmi'  # TODO shm:tmi or tmi
            self.mpiexec_global_options['I_MPI_TMI_PROVIDER'] = 'psm'
            if self.options.debuglvl > 0:
                self.mpiexec_global_options['TMI_DEBUG'] = '1'

    def mpirun_prepare_execution(self):
        """Small change"""
        # intel mpi mpirun strips the --file otion for mpdboot if it detects PBS_ENVIRONMENT to some fixed value
        # - we don't want that
        self._setenv('PBS_ENVIRONMENT', 'PBS_BATCH_MPI')

        return super(IntelMPI, self).mpirun_prepare_execution()


class IntelHydraMPI(IntelMPI):
    _mpiscriptname_for = ['ihmpirun']

    _mpirun_version = lambda x: LooseVersion(x) >= LooseVersion("4.1.0.0")
    _mpirun_version = staticmethod(_mpirun_version)

    HYDRA = True
    HYDRA_LAUNCHER_NAME = "bootstrap"

    DEVICE_MPIDEVICE_MAP = {
                            'ib':'shm:dapl',
                            'det':'det',
                            'shm':'shm',
                            'socket':'shm:sock',
                            }

    def make_mpiexec_hydra_options(self):
        super(IntelMPI, self).make_mpiexec_hydra_options()
        self.mpiexec_options.append("-perhost %d" % self.mpitotalppn)


    def mpiexec_set_global_options(self):
        """Set mpiexec global options"""
        super(IntelHydraMPI, self).mpiexec_set_global_options()
        self.mpiexec_global_options['I_MPI_FALLBACK'] = self._enable_disable(self.options.impi_fallback)

        if 'I_MPI_DEVICE' in self.mpiexec_global_options:
            del self.mpiexec_global_options['I_MPI_DEVICE']
        if not 'I_MPI_FABRICS' in self.mpiexec_global_options:
            self.mpiexec_global_options['I_MPI_FABRICS'] = self.device

        scalable_progress = (self.mpitotalppn * self.nruniquenodes) > 64
        self.mpiexec_global_options['I_MPI_DAPL_SCALABLE_PROGRESS'] = self._one_zero(scalable_progress)

        self.mpiexec_global_options['I_MPI_DAPL_UD'] = self._enable_disable(self.options.impi_daplud)


class IntelLegacy(IntelMPI):
    _mpirun_version = lambda x: LooseVersion(x) < LooseVersion("3.0.0")
    _mpirun_version = staticmethod(_mpirun_version)

    def maketunecmds(self):
        """Wrap command in Intel MPI tuning facility that generates tuned MPI parameters for the application
        """
        self.log.raiseException("Legacy code, information purposes only!")
        ans = []

        # disable tuning file!!
        self.tune = False
        # set this to manually start mpdboot
        self.mpitotalnum = self.sched.nruniq

        opts = self.getmpdboot()
        cmd = "%s %s" % ('mpdboot', ' '.join(opts))
        ans.append([cmd, False])


        rulesname = 'rules.xml'
        if not os.path.exists(rulesname):
            self.log.error("Rules file %s not found" % rulesname)
        else:
            rules = os.path.abspath(rulesname)
        envname = 'env.xml'
        if not os.path.exists(envname):
            self.log.error("Env file %s not found" % envname)
        else:
            env = os.path.abspath(envname)

        if self.debug:
            ans.append(['mpdtrace -l', False])

        opts = []
        # start mpdboot manually
        opts += ["--file %s" % self.mpdbootfile]
        opts += ["--rules %s" % rules, "--env %s" % env, "--outdir %s" % os.getcwd()]
        opts += ['--app mpiexec']
        opts += self.getmpiexec(notune=False)
        cmd = "%s %s" % ('mpitune', ' '.join(opts))
        ans.append([cmd, True, True])

        ans.append(['mpdallexit', False])

        self.log.debug("maketunecmds returns %s" % ans)
        return ans


    def gettuning(self):
        """Get a tuning config file that matches the current code"""
        self.log.raiseException("Legacy code, information purposes only!")

        ans = '-noconf'
        if not self.tune:
            self.log.debug("No tuning parameter: %s" % ans)
            return ans

        conf = None
        if os.environ.has_key('TUNINGCONF'):
            conf = os.environ['TUNINGCONF']
            self.log.debug("TUNINGCONF variable: %s" % conf)
        else:
            if not os.environ.has_key('SOFTROOTIMPI'):
                self.log.error('gettuning: environment variable SOFTROOTIMPI not found')
                return ans
            tmpdir = os.path.join(os.environ['SOFTROOTIMPI'], 'etc64')
            if not os.path.exists(tmpdir):
                self.log.error("path with configfiles %s not found" % tmpdir)
                return ans
            # <app>_<device>_nn_<#nodes>_np_<#processes>_ppn_<#processes/node>.conf
            # 2 factors: np and nn
            w = 10
            goal = w * (self.sched.nrnodes + 1) + (self.sched.nruniq + 1)
            mindist = 10 * 1000 * 1000

            if os.environ.has_key('TUNINGAPP'):
                app = os.environ['TUNINGAPP']
            else:
                app = 'mpiexec'
            import glob
            reg = re.compile(r"%s_%s_nn_(\d+)_np_(\d+)_ppn_(\d+).conf" % (app, self.dev))
            for fi in glob.glob("%s/*.conf" % (tmpdir)):
                r = reg.search(os.path.basename(fi))
                if r:
                    nn = int(r.group(1))
                    np = int(r.group(2))
                    ppn = int(r.group(3))
                    dist = abs(goal - (w * (np + 1) + (nn + 1) + (0 * ppn)))
                    if dist < mindist:
                        conf = fi
                        mindist = dist

        if conf:
            if not os.path.isfile(conf):
                self.log.error("Tuning config file %s not found" % conf)
            else:
                ans = "-tune %s" % conf
        self.log.debug("Tuning parameter: %s" % ans)
        return ans

