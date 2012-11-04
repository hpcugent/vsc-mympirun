#!/usr/bin/env python
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
Small mpi4py script that collects and prints some sanity information
    - rank information
        - affinity
        - location
        - threading environment
    - host information
"""
import os
from vsc.utils import affinity
from mpi4py import MPI
from vsc.fancylogger import getLogger, setLogLevelInfo

log = getLogger('MPI sanity')
setLogLevelInfo()

comm = MPI.COMM_WORLD

class Report(dict):
    def __init__(self, *args, **kwargs):
        super(Report, self).__init__(*args, **kwargs)
        self.update({
                     'rank': comm.rank,
                     'size':comm.size
                     })
        self.run()

    def add_affinity(self):
        self.update({
                     'affinity':[idx for idx, x in enumerate(affinity.sched_getaffinity().get_cpus()) if x == 1],
                     })

    def add_host(self):
        self.update({
                     'hostname':os.uname()[1],
                     'kernel':os.uname()[2],
                     })

    def _add_environment(self, name):
        self.update({
                     name:['%s=%s' % (k, v) for k, v in os.environ.items() if k.startswith(name)]
                     })

    def add_environment(self):
        for n in ['OMP']:
            self._add_environment(n)

    def run(self):
        self.add_affinity()
        self.add_host()
        self.add_environment()

## gather the info from all processes
recvbuf = comm.gather(Report(), 0)

if comm.rank == 0:
    ## recvbuf is list of dicts

    ## internal sanity check
    lens = [len(x) for x in recvbuf]
    if len(set(lens)) > 1:
        log.error("Not all reports contain same amount of data")
