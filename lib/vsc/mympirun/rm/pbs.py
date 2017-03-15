#
# Copyright 2009-2017 Ghent University
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
Torque / PBS
"""
import os

from vsc.mympirun.rm.sched import Sched


class PBS(Sched):

    """Torque/PBS based"""
    _sched_for = ['pbs', 'torque']
    SCHED_ENVIRON_ID = 'PBS_JOBID'
    SCHED_ENVIRON_NODEFILE = 'PBS_NODEFILE'

    # pbsssh is only used if native support for pbsdsh is not supported in the MPI library;
    # e.g. Intel MPI v5.x and newer supports using pbsdsh as launcher natively, no need for pbsssh wrapper
    RSH_LARGE_CMD = 'pbsssh'
    RSH_LARGE_LIMIT = 'pbsssh'
    HYDRA_LAUNCHER_EXEC = 'pbsssh'
    HYDRA_RMK = ['pbs']

    def set_nodes(self):

        nodevar = 'PBS_NODEFILE'
        filename = os.environ.get(nodevar, None)
        if filename is None:
            self.log.raiseException("set_nodes: failed to get %s from environment"  % nodevar)

        try:
            self.nodes = [x.strip() for x in open(filename).read().split("\n") if len(x.strip()) > 0]
            self.log.debug("set_nodes: from %s: %s", filename, self.nodes)
        except IOError:
            self.log.raiseException("set_nodes: failed to get nodes from nodefile %s" % filename)

        self.log.debug("set_nodes: %s", self.nodes)
