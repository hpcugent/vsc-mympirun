#
# Copyright 2009-2020 Ghent University
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

from vsc.mympirun.common import which
from vsc.mympirun.rm.sched import Sched
from vsc.utils.missing import nub


PBSDSH = 'pbsdsh'
PBSSSH = 'pbsssh'


class PBS(Sched):

    """Torque/PBS based"""
    _sched_for = ['pbs', 'torque']
    # these environment variables are used to detect we're running in a SLURM job environment (see what_sched function)
    SCHED_ENVIRON_ID = 'PBS_JOBID'
    SCHED_ENVIRON_NODE_INFO = 'PBS_NODEFILE'

    HYDRA_RMK = ['pbs']
    RM_HYDRA_LAUNCHER = 'pbsdsh'

    def __init__(self, *args, **kwargs):
        """PBS constructor"""
        super(PBS, self).__init__(*args, **kwargs)

        # pbsssh is only used if native support for pbsdsh is not supported in the MPI library;
        # e.g. Intel MPI v5.x and newer supports using pbsdsh as launcher natively, no need for pbsssh wrapper
        if which(PBSSSH) and which(PBSDSH):
            self.log.debug("Both 'pbsssh' and 'pbsdsh' found, so using 'pbsssh' as remote shell command.")
            self.RSH_LARGE_CMD = PBSSSH
            self.HYDRA_LAUNCHER_EXEC = PBSSSH
        elif which(PBSSSH):
            self.log.debug("Can't use '%s' wrapper if '%s' is not available", PBSDSH, PBSSSH)
        else:
            self.log.debug("'%s' wrapper not available, so can't use it", PBSSSH)

        self.log.info("Using '%s' as remote shell command", self.get_rsh())

    def set_nodes(self):

        filename = os.environ.get(self.SCHED_ENVIRON_NODE_INFO)
        if filename is None:
            self.log.raiseException("set_nodes: failed to get $%s from environment" % self.SCHED_ENVIRON_NODE_INFO)

        try:
            self.nodes = [x.strip() for x in open(filename).read().split("\n") if len(x.strip()) > 0]
            self.log.debug("set_nodes: from %s: %s", filename, self.nodes)
        except IOError:
            self.log.raiseException("set_nodes: failed to get nodes from nodefile %s" % filename)

        self.nodes_uniq = nub(self.nodes)
        self.nodes_tot_cnt = len(self.nodes)

        self.log.debug("set_nodes: %s (cnt: %d; uniq: %s)", self.nodes, self.nodes_tot_cnt, self.nodes_uniq)
