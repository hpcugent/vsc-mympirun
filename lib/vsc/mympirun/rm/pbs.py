##
# Copyright 2009-2012 Ghent University
# Copyright 2009-2012 Stijn De Weirdt
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
##

"""
Torque / PBS
"""

from vsc.mympirun.rm.sched import Sched
import os

class PBS(Sched):
    """Torque/PBS based"""
    _sched_for = ['pbs', 'torque']
    _sched_environ_id = 'PBS_JOBID'

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






