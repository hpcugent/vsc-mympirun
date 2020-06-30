#!/usr/bin/env python
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
Small mpi4py script that collects and prints some sanity information
    - rank information
        - affinity
        - location
        - threading environment
    - host information
"""
import os
import sys
from vsc.utils import affinity
from vsc.utils.fancylogger import getLogger, setLogLevelInfo

MPI4PY_EXCEPTION = None
try:
    from mpi4py import MPI
except ImportError as MPI4PY_EXCEPTION:
    pass

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
                     name:dict([('%s' % k, '%s' % v) for k, v in os.environ.items() if k.startswith(name)])
                     })

    def add_environment(self):
        for n in ['OMP']:
            self._add_environment(n)

    def run(self):
        self.add_affinity()
        self.add_host()
        self.add_environment()

def check():
    # recvbuf is list of dicts

    # internal sanity check
    lens = [len(x) for x in recvbuf]
    if len(set(lens)) > 1:
        log.error("Not all reports contain same amount of data (%s)" % (set(lens)))

    for idx, rep in enumerate(recvbuf):
        if not idx == rep['rank']:
            log.error('Report rank %s does not match gather index %s' % (rep['rank'], idx))

    # all nodes same property ?
    for prop in ['kernel']:
        props = [x[prop] for x in recvbuf]
        if len(set(props)) > 1:
            log.error("Not all ranks report identical property %s (%s)" % (prop, set(props)))

    # make nodes/rank structure
    hostnames = set([y['hostname'] for y in recvbuf])
    anodes = dict([(x, []) for x in hostnames])
    for r in recvbuf:
        anodes[r['hostname']].append(r['affinity'])

    for node, afs in anodes.items():
        # overlap in afs within a node?
        res = []
        for af in afs:
            for coreid in af:
                if coreid in res:
                    log.error("In node %s affinity overlap on core %s found" % (node, coreid))
                else:
                    res.append(coreid)

    # check OMP_NUM_THREADS setting
    omps = [x['OMP'].get('OMP_NUM_THREADS', None) for x in recvbuf]
    afs = [x['affinity']for x in recvbuf]
    # does it match the affinity ?
    if None in omps:
        log.error("OMP_NUM_THREADS not set in all ranks")
    else:
        for rank, (omp, af) in enumerate(zip(omps, afs)):
            if not len(af) == int(omp):
                log.error("OMP_NUM_THREADS set for rank %s to %s does not match affinity width %s" % (rank, omp, af))

    # check for mapping
    for idx, _ in enumerate(recvbuf):
        next_idx = (idx + 1) % len(recvbuf)
        if recvbuf[idx]['hostname'] == recvbuf[next_idx]['hostname']:
            if not recvbuf[idx]['affinity'][-1] == recvbuf[next_idx]['affinity'][0] - 1:
                log.error("No nn on same node for rank %s (aff %s) and next rank %s (aff %s)" %
                          (idx, recvbuf[idx]['affinity'], next_idx, recvbuf[next_idx]['affinity']))
        else:
            if not recvbuf[next_idx]['affinity'][0] == 0:
                log.error("No nn on different nodes for rank %s (hn %s aff %s) and next rank %s (hn %s aff %s)" %
                           (idx, recvbuf[idx]['hostname'], recvbuf[idx]['affinity'],
                            next_idx, recvbuf[next_idx]['hostname'], recvbuf[next_idx]['affinity'])
                          )


if __name__ == '__main__':
    log = getLogger('mympisanity')
    setLogLevelInfo()

    if MPI4PY_EXCEPTION:
        log.error("No mpi4py found: %s", MPI4PY_EXCEPTION)
        sys.exit(1)


    log.info("mympisanity started")

    comm = MPI.COMM_WORLD

    # gather the info from all processes
    recvbuf = comm.gather(Report(), 0)
    log.info("mympisanity gather report finished")


    if comm.rank == 0:
        check()
