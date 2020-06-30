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
Main sched class
"""
import os
import time
import random
import re

from vsc.utils.affinity import sched_getaffinity
from vsc.utils.fancylogger import getLogger
from vsc.mympirun.common import SchedBase


class Sched(SchedBase):

    """General class for scheduler/resource manager related functions."""

    # if the SCHED_ENVIRON_ID is not found, create one yourself
    AUTOGENERATE_JOBID = False

    SCHED_ENVIRON_ID = None
    SCHED_ENVIRON_NODE_INFO = None

    SAFE_RSH_CMD = 'ssh'
    SAFE_RSH_LARGE_CMD = 'sshsleep'
    RSH_CMD = None
    RSH_LARGE_CMD = None

    # nr of nodes considered large
    # relevant for internode communication for eg mpdboot
    RSH_LARGE_LIMIT = 16

    HYDRA_RMK = []
    HYDRA_LAUNCHER = 'ssh'
    HYDRA_LAUNCHER_EXEC = None
    RM_HYDRA_LAUNCHER = None

    def __init__(self, options=None, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)
        if not hasattr(self, 'options'):
            self.options = options

        self.cores_per_node = None
        self.set_cores_per_node()

        self.sched_id = None
        self.set_sched_id()

        self.cpus = []
        self.set_cpus()

        self.nodes, self.nodes_uniq, self.nodes_tot_cnt = None, None, None
        self.set_nodes()

        self.multiplier = None
        self.set_multiplier()

        ppn = os.environ.get('PBS_NUM_PPN')
        if ppn is not None:
            self.ppn = int(ppn)
            self.log.debug("Determined # cores per node via $PBS_NUM_PPN: %s" % self.ppn)
        else:
            self.ppn = len(self.cpus)
            self.log.debug("Failed to determine # cores per node via $PBS_NUM_PPN, using affinity: found %s" % self.ppn)
        self.set_ppn()

        self.mpinodes = None
        self.set_mpinodes()

        super(Sched, self).__init__(**kwargs)

    # other methods
    def set_sched_id(self):
        """Get a unique id for this scheduler. This is typically the job id"""
        if self.SCHED_ENVIRON_ID is not None:
            self.sched_id = os.environ.get(self.SCHED_ENVIRON_ID, None)

        if self.sched_id is None:
            if self.AUTOGENERATE_JOBID:
                self.log.info("set_sched_id: failed to get id from environment variable %s, will generate one.",
                              self.SCHED_ENVIRON_ID)
                self.sched_id = "SCHED_%s%s%05d" % (self.__class__.__name__, time.strftime("%Y%m%d%H%M%S"),
                                                    random.randint(0, 10 ** 5 - 1))
                self.log.debug("set_sched_id: using generated id %s", self.sched_id)
            else:
                self.log.raiseException("set_sched_id: failed to get id from environment variable %s" %
                                        self.SCHED_ENVIRON_ID)

    def set_cores_per_node(self):
        """Determine the number of available cores on this node, based on /proc/cpuinfo"""

        filename = '/proc/cpuinfo'
        regcores = re.compile(r"^processor\s*:\s*\d+\s*$", re.M)

        self.cores_per_node = len(regcores.findall(open(filename).read()))

        self.log.debug("set_cores_per_node: found %s", self.cores_per_node)

    def set_cpus(self):
        """
        Determine which cpus on the node can be used

        are we running in a cpuset?
          - and how big is it (nr of procs compared to local number of cores)

        stores local core ids in array
        """

        try:
            proc_affinity = sched_getaffinity()  # get affinity for current proc
            self.cpus = [idx for idx, cpu in enumerate(proc_affinity.cpus) if cpu == 1]
            self.log.debug("found cpus from affinity: %s", self.cpus)
        except Exception:
            self.cpus = range(self.cores_per_node)
            self.log.debug("could not find cpus from affinity, simulating with range(cores_per_node): %s", self.cpus)

    def set_nodes(self):
        """get a list with the node of every requested processor/core"""
        self.log.raiseException("set_nodes not implemented")

    def set_ppn(self):
        """Determine the processors per node, based on the list of nodes and the list of unique nodes"""
        self.ppn_dict = {}
        for node in self.nodes:
            self.ppn_dict.setdefault(node, 0)
            self.ppn_dict[node] += 1
        self.log.debug("Number of processors per node: %s" % self.ppn_dict)

    def get_rsh(self):
        """Determine remote shell command"""
        if hasattr(self.options, 'ssh') and self.options.ssh:
            # some safe fallback based on ssh
            if self.is_large():
                rsh = self.SAFE_RSH_LARGE_CMD
            else:
                rsh = self.SAFE_RSH_CMD
        else:
            # optimised
            # set in MPI, not in RM
            if getattr(self, 'has_hydra', None):
                rsh = 'ssh'  # default anyway
            elif self.is_large():
                rsh = self.RSH_LARGE_CMD
            else:
                rsh = self.RSH_CMD

        self.log.debug("get_rsh returns %s", rsh)
        return rsh

    def is_large(self):
        """Determine if this is a large job or not"""

        res = ((self.nodes_tot_cnt > self.RSH_LARGE_LIMIT) and
               (any(c == self.cores_per_node for c in self.ppn_dict.values())))
        self.log.debug("is_large returns %s", res)
        return res

    def set_multiplier(self):
        """set multiplier """
        if self.options.multi:
            self.multiplier = self.options.multi
        elif self.options.double:
            self.multiplier = 2
        else:
            self.multiplier = 1

    def set_mpinodes(self):
        """
        Make a list of nodes that MPI should use

        Calculates the amount of mpi processes based on the processors per node and options like double and hybrid
        Will also make a list with nodes, where each entry is supposed to run an mpi process
        """

        res = []
        if self.options.hybrid is None:
            res = self.nodes * self.multiplier
        else:
            for uniquenode in self.nodes_uniq:
                res.extend([uniquenode] * self.options.hybrid * self.multiplier)

        # reorder
        ordermode = getattr(self.options, 'order', None)
        if ordermode is None:
            ordermode = 'normal'
        ordermode = ordermode.split("_")
        if ordermode[0] in ('normal',):
            # do nothing
            self.log.debug("set_mpinodes: no reordering (mode %s)", ordermode)
        elif ordermode[0] in ('random',):
            if len(ordermode) == 2:
                seed = int(ordermode[1])
                random.seed(seed)
                self.log.debug("set_mpinodes: setting random seed %s", seed)
            random.shuffle(res)
            self.log.debug("set_mpinodes shuffled nodes (mode %s)" %
                           ordermode)
        elif ordermode[0] in ('sort',):
            res.sort()
            self.log.debug("set_mpinodes sort nodes (mode %s)", ordermode)
        else:
            self.log.raiseException("set_mpinodes unknown ordermode %s" % ordermode)

        self.mpinodes = res

    def is_local(self):
        """
        Return whether this is a local scheduler or not.
        """
        return False
