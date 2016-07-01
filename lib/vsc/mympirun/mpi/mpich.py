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
MPICH specific classes
"""

from distutils.version import LooseVersion

from vsc.mympirun.mpi.mpi import MPI
from vsc.utils.run import run_simple


class MVAPICH2Hydra(MPI):
    _mpiscriptname_for = ['mhmpirun']
    _mpirun_for = ['MVAPICH2']
    _mpirun_version = lambda x: LooseVersion(x) >= LooseVersion("1.6.0")
    _mpirun_version = staticmethod(_mpirun_version)

    HYDRA = True

    PASS_VARIABLES_CLASS_PREFIX = ['MV2', 'HYDRA']

    MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION = "-envlist %(commaseparated)s"

    def prepare(self):
        super(MVAPICH2Hydra, self).prepare()

        if self.options.pinmpi:
            os.environ['MV2_ENABLE_AFFINITY'] = 1
            os.environ['MV2_CPU_BINDING_POLICY'] = 'bunch'
        else:
            os.environ['MV2_ENABLE_AFFINITY'] = 0

    def mpiexec_set_global_options(self):
        """Set mpiexec global options"""
        if self.options.debuglvl > 0 and self.options.qlogic_ipath:
            self.mpiexec_global_options['MV2_PSM_DEBUG'] = 1

        super(MVAPICH2Hydra, self).mpiexec_set_global_options()

    def _make_final_mpirun_cmd(self):
        """Create the acual mpirun command
            add it to self.mpirun_cmd
            No mpdboot for openmpi
        """
        self.mpirun_cmd += self.mpiexec_options


class MVAPICH2(MVAPICH2Hydra):
    """
    MVAPICH2 from 1.6 has new style of starting (wrt 1.4)
    - it uses the hydra interface and sligthly other mpdboot
    """
    _mpiscriptname_for = ['mmpirun']
    _mpirun_for = ['MVAPICH2']
    _mpirun_version = lambda x: LooseVersion(x) < LooseVersion("1.6.0")
    _mpirun_version = staticmethod(_mpirun_version)

    HYDRA = False

    PASS_VARIABLES_CLASS_PREFIX = ['MV2']


    def make_mpdboot_options(self):
        """Small fix"""
        self.mpdboot_totalnum = self.nruniquenodes

        super(MVAPICH2, self).make_mpdboot_options()

    def mpirun_prepare_execution(self):
        """Manual start/stop of mpdboot"""

        res = []

        cmd = "%s %s" % ('mpdboot', ' '.join(self.mpdboot_options))
        res.append((run_simple, cmd))

        if self.options.debug:
            res.append((run_simple, 'mpdtrace -l'))

        res += super(MVAPICH2, self).mpirun_prepare_execution

        res.append((run_simple, 'mpdallexit'))


class MPICH2Hydra(MVAPICH2Hydra):
    _mpiscriptname_for = ['m2hmpirun']
    _mpirun_for = ['MPICH2', 'mpich2']
    _mpirun_version = lambda x: LooseVersion(x) >= LooseVersion("1.4.0")
    _mpirun_version = staticmethod(_mpirun_version)

    PASS_VARIABLES_CLASS_PREFIX = ['MPICH']

    def mpiexec_get_global_options(self):
        # add pinning
        options = super(MPICH2Hydra, self).mpiexec_get_global_options()
        if self.options.pinmpi:
            options.extend(['-binding', 'rr' , '-topolib' , 'hwloc'])
        return options

class MPICH2(MVAPICH2):
    _mpiscriptname_for = ['m2mpirun']
    _mpirun_for = ['MPICH2', 'mpich2']
    _mpirun_version = lambda x: LooseVersion(x) < LooseVersion("1.4.0")
    _mpirun_version = staticmethod(_mpirun_version)

    PASS_VARIABLES_CLASS_PREFIX = ['MPICH']

    def mpiexec_get_global_options(self):
        # add pinning
        options = super(MPICH2Hydra, self).mpiexec_get_global_options()
        if self.options.pinmpi:
            options.extend(['-binding', 'rr' , '-topolib' , 'hwloc'])
        return options
