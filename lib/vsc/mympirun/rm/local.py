##
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
Local scheduler : no scheduler, act on single node
"""

from vsc.mympirun.rm.sched import Sched
import time
import random

class Local(Sched):
    """
    Local class for local debugging (ie no scheduler settings)
    - will use the amount of cores found on localhost.
    """
    _sched_for = ['local']

    HYDRA_LAUNCHER = ['local']
    ## don't set _sched_environ_test. This one should always work, and will not be guessed. It will be fallback or requested.

    def get_id(self):
        self.id = "SCHED_Local%s%05d" % (time.strftime("%Y%m%d%H%M%S"), random.randint(0, 10 ** 5 - 1))
        self.log.debug("get_id id %s" % self.id)

    def get_node_list(self):
        """Get the hostnames for the localnode
            MPIRUN_LOCALHOSTNAME is from multiple inheritance with MPI class
        """

        localhostname = getattr(self, 'MPIRUN_LOCALHOSTNAME', 'localhost')
        self.nodes = [localhostname] * self.foundppn
        self.nrnodes = len(self.nodes)

        self.log.debug("get_node_list: set %s nodes: %s" % (self.nrnodes, self.nodes))

