#
# Copyright 2018-2018 Ghent University
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
SLURM
"""
import os
import re

from vsc.mympirun.mpi.mpi import which
from vsc.mympirun.rm.sched import Sched
from vsc.utils.run import run_simple


class SLURM(Sched):
    """SLURM"""

    _sched_for = ['slurm']
    # these environment variables are used to detect we're running in a SLURM job environment (see what_sched function)
    SCHED_ENVIRON_ID = 'SLURM_JOBID'
    SCHED_ENVIRON_NODE_INFO = 'SLURM_NODELIST'

    HYDRA_RMK = ['slurm']

    def set_nodes(self):
        """Set list of nodes available in current environment."""

        # based on https://github.com/SchedMD/slurm/blob/master/contribs/torque/generate_pbs_nodefile.pl

        # determine list of hostnames involved in job via "scontrol show hostname $SLURM_NODELIST"
        nodelist = os.environ.get(self.SCHED_ENVIRON_NODE_INFO)
        if nodelist is None:
            self.log.raiseException("set_nodes: failed to get $%s from environment" % self.SCHED_ENVIRON_NODE_INFO)
        else:
            self.log.debug("set_nodes: obtained $%s value: %s", self.SCHED_ENVIRON_NODE_INFO, nodelist)

        cmd = "scontrol show hostname %s" % nodelist
        ec, out = run_simple(cmd)
        if ec:
            self.raiseException("set_nodes: failed to get full list of unique hostnames using '%s': %s" % (cmd, out))
        else:
            self.nodes_uniq = out.strip().split('\n')

        tpn_key = 'SLURM_TASKS_PER_NODE'
        tpn_spec = os.environ.get(tpn_key)
        if tpn_spec is None:
            self.log.raiseException("set_nodes: failed to get $%s from environment" % tpn_key)
        else:
            self.log.debug("set_nodes: obtained $%s value: %s", tpn_key, tpn_spec)
            tasks_per_node = []
            # duplicate counts are compacted into something like '2(x3)', so we unroll those
            compact_regex = re.compile(r'^(?P<task_cnt>\d+)\(x(?P<repeat_cnt>\d+)\)$')
            for entry in tpn_spec.split(','):
                res = compact_regex.match(entry)
                if res:
                    tasks_per_node.extend([int(res.group('task_cnt'))] * int(res.group('repeat_cnt')))
                else:
                    tasks_per_node.append(int(entry))
            self.log.debug("set_nodes: tasks_per_node: %s" % tasks_per_node)

        if len(self.nodes_uniq) != len(tasks_per_node):
            self.raiseException("nodes_uniq vs tasks_per_node mismatch: %s vs %s" % (self.nodes_uniq, tasks_per_node))

        self.nodes_tot_cnt = sum(tasks_per_node)

        self.nodes = []
        for (node, task_cnt) in zip(self.nodes_uniq, tasks_per_node):
            self.nodes.extend([node] * task_cnt)

        self.log.debug("set_nodes: %s (cnt: %d; uniq: %s)", self.nodes, self.nodes_tot_cnt, self.nodes_uniq)
