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
MPICH specific classes

Documentation can be found at https://www.mpich.org/documentation/guides/
"""
import os

from vsc.mympirun.common import version_in_range
from vsc.mympirun.mpi.mpi import MPI
from vsc.utils.run import run


class MVAPICH2Hydra(MPI):

    """An implementation of the MPI class for MVAPICH2 with Hydra"""

    _mpiscriptname_for = ['mhmpirun']
    _mpirun_for = 'MVAPICH2'
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '1.6.0', None))

    HYDRA = True

    OPTS_FROM_ENV_FLAVOR_PREFIX = ['MV2', 'HYDRA']

    OPTS_FROM_ENV_TEMPLATE = ['-envlist', '%(commaseparated)s']

    def prepare(self):
        super(MVAPICH2Hydra, self).prepare()

        if self.options.pinmpi:
            os.environ['MV2_ENABLE_AFFINITY'] = "1"
            os.environ['MV2_CPU_BINDING_POLICY'] = 'bunch'
        else:
            os.environ['MV2_ENABLE_AFFINITY'] = "0"

    def set_mpiexec_global_options(self):
        """Set mpiexec global options"""
        if self.options.debuglvl > 0 and self.options.use_psm:
            self.mpiexec_global_options['MV2_PSM_DEBUG'] = 1

        super(MVAPICH2Hydra, self).set_mpiexec_global_options()

    def _make_final_mpirun_cmd(self):
        """
        Create the acual mpirun command
        MVAPICH2Hydra doesn't need mpdboot options
        """
        self.mpirun_cmd.add(self.mpiexec_options)


class MVAPICH2(MVAPICH2Hydra):

    """
    MVAPICH2 from 1.6 has new style of starting (wrt 1.4)
      - it uses the hydra interface and sligthly other mpdboot
    """
    _mpiscriptname_for = ['mmpirun']
    _mpirun_for = 'MVAPICH2'
    staticmethod(lambda ver: version_in_range(ver, None, '1.6.0'))

    HYDRA = False

    OPTS_FROM_ENV_FLAVOR_PREFIX = ['MV2']

    def make_mpdboot_options(self):
        """Small fix"""

        self.mpdboot_options.add("--totalnum=%s" % len(self.nodes_uniq))

        super(MVAPICH2, self).make_mpdboot_options()

    def mpirun_prepare_execution(self):
        """Manual start/stop of mpdboot"""

        res = []

        cmd = "%s %s" % ('mpdboot', ' '.join(self.mpdboot_options))
        res.append((run, cmd))

        if self.options.debug:
            res.append((run, 'mpdtrace -l'))

        res += super(MVAPICH2, self).mpirun_prepare_execution

        res.append((run, 'mpdallexit'))


class MPICH2Hydra(MVAPICH2Hydra):

    """An implementation of the MPI class for MPICH2 with Hydra"""

    _mpiscriptname_for = ['m2hmpirun']
    _mpirun_for = 'MPICH2'
    staticmethod(lambda ver: version_in_range(ver, '1.4.0', None))

    OPTS_FROM_ENV_FLAVOR_PREFIX = ['MPICH']

    def get_mpiexec_global_options(self):
        # add pinning
        options = super(MPICH2Hydra, self).get_mpiexec_global_options()
        if self.options.pinmpi:
            options.add(['-binding', 'rr', '-topolib', 'hwloc'])
        return options


class MPICH2(MVAPICH2):

    """An implementation of the MPI class for MPICH2"""

    _mpiscriptname_for = ['m2mpirun']
    _mpirun_for = 'MPICH2'
    staticmethod(lambda ver: version_in_range(ver, None, '1.4.0'))

    OPTS_FROM_ENV_FLAVOR_PREFIX = ['MPICH']

    def get_mpiexec_global_options(self):
        # add pinning
        options = super(MPICH2, self).get_mpiexec_global_options()
        if self.options.pinmpi:
            options.add(['-binding', 'rr', '-topolib', 'hwloc'])
        return options
