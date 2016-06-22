#
# Copyright 2009-2016 Ghent University
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

from vsc.mympirun.rm.sched import Sched
import os

class PBS(Sched):
    """Torque/PBS based"""
    _sched_for = ['pbs', 'torque']
    SCHED_ENVIRON_ID = 'PBS_JOBID'

    RSH_LARGE_CMD = 'pbsssh'
    RSH_LARGE_LIMIT = 'pbsssh'
    HYDRA_LAUNCHER_EXEC = 'pbsssh'
    HYDRA_RMK = ['pbs']

    def get_node_list(self):

        nodevar = 'PBS_NODEFILE'
        fn = os.environ.get(nodevar, None)
        if fn is None:
            self.log.raiseException("get_node_list: failed to get %s from environment" % nodevar)

        try:
            self.nodes = [ x.strip() for x in file(fn).read().split("\n") if len(x.strip()) > 0]
            self.nrnodes = len(self.nodes)
            self.log.debug("get_node_list: found %s nodes in %s: %s" % (self.nrnodes, fn, self.nodes))
        except:
            self.log.raiseException("get_node_list: failed to get nodes from nodefile %s" % fn)

        self.log.debug("get_node_list: set %s nodes: %s" % (self.nrnodes, self.nodes))






