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
from vsc.mympirun.common import SchedKlass
from vsc.utils.run import run_file, async_to_stdout


class Sched(SchedKlass):
    LAUNCHER = None

    def __init__(self, options=None, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)
        if not hasattr(self, 'options'):
            self.options = options

        self.sched_id = None
        self.set_sched_id()

        super(Sched, self).__init__(**kwargs)

    def set_sched_id(self):
        """get a unique id for this scheduler"""
        self.sched_id = os.environ.get(self.SCHED_ENVIRON_ID, None)

    def pmicmd(self, envs):
        """
        Return generated pmi command (as list) and the run function
        envs is list of variable names that is modified
        """
        pmicmd = [self.LAUNCHER]

        for name in ['sizing', 'environment', 'mpi']:
            mthd = 'pmicmd_' + name
            margs = []
            if name == 'environment':
                margs.append(envs)

            args = getattr(self, mthd)(*margs)
            self.log.debug("Generated pmicmd %s arguments %s", name, args)
            pmicmd += args

        run_function, run_function_args = self.run_function()
        pmicmd += run_function_args

        pmicmd += ['--' + x for x in getattr(self.options, 'pass', [])]  # .pass gives syntax error?

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

    def pmicmd_sizing(self):
        """Generate the sizing arguments to the launcher as a list"""
        return []

    def pmicmd_environment(self, envs):  # pylint:disable=unused-argument
        """Generate the environment related arguments to the launcher as a list"""
        # ignore the envs for now
        return []

    def pmicmd_mpi(self):
        """Generate the mpi related arguments to the launcher as a list"""
        return []
