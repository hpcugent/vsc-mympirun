#
# Copyright 2019-2020 Ghent University
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
Base PMI Sched class, all actual classes should inherit from this one

The role of the Sched class is mainly to construct the correct sched-specific PMI call
"""

import os
from copy import deepcopy
from vsc.utils.fancylogger import getLogger
from vsc.mympirun.common import SchedBase
from vsc.utils.run import run_file, async_to_stdout


class Info(object):
    def __init__(self, nodes=None, cores=None, ranks=None, mem=None, gpus=None):
        """Initialise with
        Total:
            nodes: total number of nodes
        Per node:
            cores: number of cores per node
            ranks: number of MPI ranks per node
            mem: memory per node
            gpus: number of gpus per node: None means no GPUs present, 0 means don't use GPUs
        """
        self.nodes = nodes
        self.cores = cores
        self.ranks = ranks
        self.mem = mem
        self.gpus = gpus

    def __str__(self):
        """Human readable"""
        return "%s nodes; with per node %s cores, %s ranks, %s mem, %s gpus" % (
            self.nodes, self.cores, self.ranks, self.mem, self.gpus)

    def deepcopy(self):
        """Return a (deep)copy"""
        return deepcopy(self)


class Sched(SchedBase):
    LAUNCHER = None

    def __init__(self, options=None, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)
        if not hasattr(self, 'options'):
            self.options = options

        self.envs = []  # list of enviroment variable names that are modified

        super(Sched, self).__init__(**kwargs)

    def set_env(self, key, value, keep=False):
        """
        Set os.environ and track variable
        If keep is True, don't override existing value
        """
        current = os.environ.get(key)
        if keep and current is not None:
            self.log.debug("Keeping existing environment variable %s with value %s (ignore value %s)",
                           key, current, value)
        else:
            os.environ[key] = str(value)
            self.envs.append(key)
            self.log.debug("Set environment variable %s: %s", key, value)

    def pmicmd(self):
        """
        Return generated pmi command (as list) and the run function
        envs is list of variable names that are modified
        """
        pmicmd = [self.LAUNCHER]

        # the mpi calls should only set environment variables
        for name in ['tune', 'pmi', 'debug']:
            method_name = 'mpi_' + name
            getattr(self, method_name)()
            self.log.debug("Calling %s", method_name)

        for name in ['sched', 'sizing', 'environment', 'mpi', 'debug']:
            args = getattr(self, 'pmicmd_' + name)()
            self.log.debug("Generated pmicmd %s arguments %s", name, args)
            pmicmd.extend(args)

        run_function, run_function_args = self.run_function()
        pmicmd.extend(run_function_args)

        pmicmd.extend(['--' + x for x in getattr(self.options, 'pass', [])])  # .pass gives syntax error?

        self.log.debug("Generated pmicmd %s", pmicmd)
        return pmicmd, run_function

    def run_function(self):
        """
        Return required run function and run function related args as list
        """
        if self.options.output:
            def run_output(cmd, **kwargs):
                kwargs['filename'] = self.options.output
                return run_file(cmd, **kwargs)
            return run_output, []
        else:
            return async_to_stdout, []

    def pmicmd_sched(self):
        """Generate the sched related arguments to the launcher as a list"""
        return []

    def job_info(self, job_info):
        """
        Fill in/complete/edit job_info dict and return it
        """
        self.log.warn("Nothing done with job_info %s", job_info)
        return job_info

    def pmicmd_size_args(self, mpi_info):
        """
        Convert mpi_info into launcher list of args
        """
        self.log.warn("Nothing done with mpi_info %s, no args generated", mpi_info)
        return []

    def pmicmd_sizing(self):
        """Generate the sizing arguments to the launcher as a list"""
        job_info = self.job_info(Info())
        self.log.debug("Got job info %s", job_info)

        # compute requested
        mpi_info = self.mpi_size(job_info)
        self.log.debug("Got mpi size info %s", mpi_info)

        # generate args
        args = self.pmicmd_size_args(mpi_info)
        self.log.debug("Got pmi cmd args %s", args)

        return args

    def pmicmd_environment(self):
        """
        Generate the environment related arguments to the launcher as a list

        Modified envs should be tracked via self.envs
        """
        self.log.debug("No environment specific arguments (assuming whole environment is used)")
        return []

    def pmicmd_mpi(self):
        """Generate the mpi related arguments to the launcher as a list"""
        return []

    def pmicmd_debug(self):
        """Generate the debug related arguments to the launcher as a list"""
        return []
