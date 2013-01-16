# #
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
# #

"""
Main sched class
"""


import os
import random
import re
from vsc.fancylogger import getLogger
from vsc.mympirun.mpi.mpi import get_subclasses
from vsc.utils.missing import nub

def whatSched(requested):
    """Return the scheduler class"""
    found_sched = get_subclasses(Sched)
    for sched in found_sched:
        # print sched.__name__, requested
        if sched._is_sched_for(requested):
            return sched, found_sched
    return None, found_sched


class Sched(object):
    """General class for scheduler/resource manager related functions."""
    _sched_for = []  # classname is default added
    _sched_environ_test = []
    _sched_environ_id = None

    SAFE_RSH_CMD = 'ssh'
    SAFE_RSH_LARGE_CMD = 'sshsleep'
    RSH_CMD = None
    RSH_LARGE_CMD = None
    RSH_LARGE_LIMIT = 16  # # nrof nodes considered large (relevant for internode communication for eg mpdboot)

    HYDRA_RMK = []
    HYDRA_LAUNCHER = ['ssh']
    HYDRA_LAUNCHER_EXEC = None


    def __init__(self, options=None, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)
        if not hasattr(self, 'options'):
            self.options = options

        self.nodes = None
        self.nrnodes = None

        self.uniquenodes = None
        self.nruniquenodes = None

        self.mpinodes = None
        self.mpinrnodes = None
        self.mpitotalppn = None

        self.id = None

        self.foundppn = None
        self.ppn = None
        self.totalppn = None

        self.cpus = []

        # # collect data
        self.get_id()
        self.cores_on_this_node()
        self.which_cpus()

        self.get_node_list()
        self.get_unique_nodes()
        self.set_ppn()

        super(Sched, self).__init__(**kwargs)


    # # TODO these will also need a factory method to verify or guess the requested mode
    # # factory methods for MPI
    # to add a new MPI class just create a new class that extends the cluster class
    # see http://stackoverflow.com/questions/456672/class-factory-in-python
    # classmethod
    def _is_sched_for(cls, name=None):
        """see if this class can provide support for sched class"""
        if name is not None:
            return name in cls._sched_for + [cls.__name__]  # # add class name as default

        # # guess it from environment
        totest = cls._sched_environ_test
        if cls._sched_environ_id is not None:
            totest.append(cls._sched_environ_id)

        for envvar in totest:
            envval = os.environ.get(envvar, None)
            if envval is None or len(envval) == 0:
                continue
            else:
                return True

        return False
    _is_sched_for = classmethod(_is_sched_for)

    # # other methods
    def get_unique_nodes(self, nodes=None):
        """Set unique nodes from self.nodes"""
        if nodes is None:
            nodes = self.nodes

        # don't use set(), preserve order!
        self.uniquenodes = nub(nodes)
        self.nruniquenodes = len(self.uniquenodes)

        self.log.debug("get_unique_nodes: %s uniquenodes: %s from %s" % (self.nruniquenodes, self.uniquenodes, nodes))

    def get_node_list(self):
        """get list of nodes (one node per requested processor/core)"""
        self.log.raiseException("get_node_list not implemented")

    def get_id(self):
        """get unique id"""
        try:
            self.id = os.environ.get(self._sched_environ_id)
        except:
            self.log.raiseException("get_id: failed to get id %s from environment" % self._sched_environ_id)

    def set_ppn(self):
        """Determine the ppn from nodes and unique nodes"""
        if self.nrnodes is None:
            self.get_node_list()
        if self.nruniquenodes is None:
            self.get_unique_nodes()

        self.ppn = self.nrnodes // self.nruniquenodes
        # # set default
        self.totalppn = self.ppn

        self.log.debug("Set ppn to %s (totalppn %s)" % (self.ppn, self.totalppn))

    def cores_on_this_node(self):
        """Determine the number of available cores on this node based on /proc/cpuinfo"""
        fn = '/proc/cpuinfo'
        regcores = re.compile(r"^processor\s*:\s*\d+\s*$", re.M)

        self.foundppn = len(regcores.findall(file(fn).read()))

        self.log.debug("coresOnThisnode: found %s" % self.foundppn)


    def which_cpus(self):
        """
        Determine which cpus can be used

        are we running in a cpuset?
        - and how big is it (nr of procs compared to local number of cores)

        stores local core ids in array
        ## TODO fix remote cpusets
        - what with remote ones?
        """
        if self.foundppn is None:
            self.cores_on_this_node()
        self.cpus = range(self.foundppn)

        cpusetprefix = '/dev/cpuset'  # # should be mounted
        myproccpuset = "/proc/%s/cpuset" % os.getpid()
        if os.path.isfile(myproccpuset):
            mycpusetsuffix = open(myproccpuset).read().strip()
            mycpuset = os.path.join(cpusetprefix, mycpusetsuffix.strip(os.sep))
            cpusetfn = os.path.join(mycpuset, 'cpus')
            if os.path.isfile(cpusetfn):
                self.log.debug("which_cpus: found cpuset %s" % (cpusetfn))
                mycpus = [x.split('-') for x in open(cpusetfn).read().strip().split(',')]
                self.cpus = []
                for cpurange in mycpus:
                    if len(cpurange) == 1:
                        self.cpus.append(int(cpurange[0]))
                    else:
                        self.cpus.extend(range(int(cpurange[0]), int(cpurange[1]) + 1))  # # range is inclusive
            else:
                self.log.debug("which_cpus: found proccpuset %s but no cpus file %s" % (myproccpuset, cpusetfn))
        else:
            self.log.debug("which_cpus: no proc cpuset %s found" % (myproccpuset))


        self.log.debug("which_cpus: using cpus %s" % (self.cpus))

    def is_large(self):
        """Determine if this is a large job or not"""
        if self.nrnodes is None:
            self.get_node_list()
        if self.foundppn is None:
            self.cores_on_this_node()

        res = (self.nrnodes > self.RSH_LARGE_LIMIT) and (self.ppn == self.foundppn)
        self.log.debug("is_large returns %s" % res)
        return res

    def get_rsh(self):
        """Determine remote shell command"""
        if hasattr(self.options, 'ssh') and self.options.ssh:
            # # some safe fallback based on ssh
            if self.is_large():
                rsh = self.SAFE_RSH_LARGE_CMD
            else:
                rsh = self.SAFE_RSH_CMD
        else:
            # # optimised
            default_rsh = getattr(self, 'DEFAULT_RSH', None)  # # set in MPI, not in RM
            if default_rsh is not None:
                rsh = default_rsh
            elif getattr(self, 'HYDRA', None):
                rsh = 'ssh'  # # default anyway
            elif self.is_large():
                rsh = self.RSH_LARGE_CMD
            else:
                rsh = self.RSH_CMD

        self.log.debug("get_rsh returns %s" % rsh)
        return rsh

    def make_node_list(self):
        """Make a modified list of nodes based on requested options"""
        if self.nodes is None:
            self.get_node_list()
        if self.totalppn is None or self.ppn is None:
            self.set_ppn()
        if self.uniquenodes is None:
            self.get_unique_nodes()

        # # get the working mode from options
        hybrid = getattr(self.options, 'hybrid', None)
        double = getattr(self.options, 'double', False)

        # # set the multiplier
        if hybrid:
            multi = hybrid
        elif double:
            multi = 2
        else:
            multi = 1

        self.log.debug("make_node_list: hybrid %s double %s multi %s" % (hybrid, double, multi))

        res = []
        if double:
            self.mpitotalppn = self.ppn * multi
            res = self.nodes * multi
        elif hybrid:
            # # return multi unique nodes
            # # mpitotalppn = 1 per node * multi
            self.mpitotalppn = multi
            for n in self.uniquenodes:
                res.extend([n] * multi)
        else:
            # # default mode
            self.mpitotalppn = self.ppn * multi
            for n in self.uniquenodes:
                res.extend([n] * self.mpitotalppn)

        # # reorder
        ordermode = getattr(self.options, 'order', None)
        if ordermode is None:
            ordermode = 'normal'
        ordermode = ordermode.split("_")
        if ordermode[0] in ('normal',):
            # # do nothing
            self.log.debug("make_node_list: no reordering (mode %s)" % ordermode)
        elif ordermode[0] in ('random',):
            if len(ordermode) == 2:
                seed = int(ordermode[1])
                random.seed(seed)
                self.log.debug("make_node_list: setting random seed %s" % seed)
            random.shuffle(res)
            self.log.debug("make_node_list shuffled nodes (mode %s)" % ordermode)
        elif ordermode[0] in ('sort',):
            res.sort()
            self.log.debug("make_node_list sort nodes (mode %s)" % ordermode)
        else:
            self.log.raiseExcepetion("make_node_list unknown ordermode %s" % ordermode)

        self.log.debug("make_node_list: ordered node list %s (mpitotalppn %s)" % (res, self.mpitotalppn))

        self.mpinodes = res
        self.nrmpinodes = len(res)


