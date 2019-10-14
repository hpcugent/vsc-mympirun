#
# Copyright 2019-2019 Ghent University
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
from vsc.utils.fancylogger import getLogger
from vsc.mympirun.common import SchedBase
from vsc.utils.run import run_file, async_to_stdout

# simple intermediate representation of the job resources
JOB_INFO = {
    'tnodes': None,  # total number of nodes
    'ncores': None,  # number of cores per node
    'nranks': None, # number of MPI ranks per node
    'nmem': None,  # memory per node
    'ngpus': None,  # number of gpus per node: None means no GPUs present, 0 means don't use GPUs
}

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

    def sane_job_info(self, info, hdr='info'):
        """
        info dict (e.g. job_info and mpi_info dicts) must match the JOB_INFO template
        to make sure that after passing around and manipulation no unexpected data appears
        or expected data disappear.
        """
        expected_keys = set(JOB_INFO.keys())
        info_keys = set(info.keys())
        if expected_keys == info_keys:
            self.log.debug("%s is sane", hdr)
        else:
            unexpected_keys = info_keys - expected_keys
            if unexpected_keys:
                self.log.raiseException("Keys %s only in %s, not in JOB_INFO" % (hdr, sorted(unexpected_keys)))
            missing_keys = expected_keys - info_keys
            if missing_keys:
                self.log.raiseException("Keys %s only in JOB_INFO, not in %s" % (hdr, sorted(missing_keys)))

    def pmicmd_sizing(self):
        """Generate the sizing arguments to the launcher as a list"""
        job_info = self.job_info(JOB_INFO.copy())

        self.sane_job_info(job_info, hdr='job_info')
        self.log.debug("Got job info %s", job_info)

        # compute requested
        mpi_info = self.mpi_size(job_info)

        self.sane_job_info(mpi_info, hdr='mpi_info')
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
