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
Local scheduler : no scheduler, act on single node
"""
from vsc.mympirun.rm.sched import Sched


class Local(Sched):

    """
    Local class for local debugging (ie no scheduler settings)
      - will use the amount of cores found on localhost.
    """
    _sched_for = ['local']
    SCHED_ENVIRON_ID = None
    SCHED_ENVIRON_NODEFILE = None
    AUTOGENERATE_JOBID = True

    HYDRA_LAUNCHER = 'local'

    def set_nodes(self):
        """
        Get the hostnames for the localnode
        MPIRUN_LOCALHOSTNAME is from multiple inheritance with MPI class
        """

        localhostname = getattr(self, 'MPIRUN_LOCALHOSTNAME', 'localhost')
        self.nodes = [localhostname] * len(self.cpus)

        self.log.debug("set_nodes: %s", self.nodes)

    def is_local(self):
        """
        Return whether this is a local scheduler or not.
        """
        return True
