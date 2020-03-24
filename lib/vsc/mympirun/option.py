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
Optionparser for mympirun
"""
from __future__ import print_function

import copy
import os

from vsc.utils import fancylogger
from vsc.utils.generaloption import GeneralOption
from vsc.utils.missing import get_subclasses


# introduce usage / -u option. (original has -h for --hybrid)
class MympirunParser(GeneralOption.PARSER):
    """Simple class to implement other help messages"""
    shorthelp = ('u', '--shorthelp', '--usage',)
    longhelp = ('U', '--help',)


class CommonOption(GeneralOption):
    """
    Parses commandline options and sets them to variables
    """
    PARSER = MympirunParser
    ALLOPTSMANDATORY = False  # eg scriptname and other options. same for mpirun options
    INTERSPERSED = False  # Stop parsing cmdline, all others opts are opts for the exe
    DESCRIPTION = None
    MPI_CLASS = None
    OPTIONS = {}  # to customize
    BASE_OPTIONS = {
        # long option: (description, type, action, default, short option)

        "debuglvl": ("Specify debug level", "int", "store", 0),

        "debugmpi": ("Enable MPI level debugging", None, "store_true", False),  # TODO PMI

        "dry-run": ("Dry run mode, just print command that will be executed", None, 'store_true', False, 'D'),

        "hybrid": ("Run in hybrid mode, specify number of processes per node.", "int", "store", None, 'h'),

        "logtofile": ("redirect the logging to a file (instead of stdout/stderr)", "str", "store", None),

        "multi": ("Run the amount of processes multiplied by the given integer", "int", "store", None),  # TODO PMI

        "output": ("redirect the output of mpirun to a file (instead of stdout/stderr)",
                   "str", "store", None),

        "setsched": ("Specify scheduler (eg local, pbs...; will try to guess by default).",
                      "str", "store", None, "S"),

        "setmpi": ("Specify MPI flavor (eg mpich2, openmpi...; will try to guess by default).",
                   "str", "store", None, "M"),

        "showmpi": ("Print the known MPI classes and exit", None, "store_true", False, 'm'),

        "showsched": ("Print the known Sched classes and exit", None, "store_true", False, 's'),

        "stats": ("Set MPI statistics level", "int", "store", 0),  # TODO PMI

    }

    def __init__(self, ismpirun=False):
        self.mpirunmode = ismpirun

        GeneralOption.__init__(self)

    def _modify_base_options(self, base_opts):
        """Hook to modify base options, e.g. change help text"""
        return base_opts

    def make_init(self):
        """ add all the options to generaloption, so it can correctly parse the command line arguments """

        opts = self._modify_base_options(copy.deepcopy(self.BASE_OPTIONS))
        opts.update(self.OPTIONS)

        prefix = ''
        self.log.debug("Add advanced option parser: options %s, description %s, prefix %s",
                       opts, self.DESCRIPTION, prefix)
        self.add_group_parser(opts, self.DESCRIPTION, prefix=prefix)

        # for all MPI classes, get the additional options
        for mpi in get_subclasses(self.MPI_CLASS):
            if mpi.RUNTIMEOPTION is not None:
                # don't try to add the same set of options twice (based on prefix)
                prefix = mpi.RUNTIMEOPTION['prefix']
                if prefix not in self.dict_by_prefix():
                    opts = mpi.RUNTIMEOPTION['options']
                    descr = mpi.RUNTIMEOPTION['description']
                    self.log.debug("Add MPI subclass %s option parser prefix %s descr %s opts %s",
                                   mpi.__name__, prefix, descr, opts)
                    self.add_group_parser(opts, descr, prefix=prefix)

    def parseoptions(self, options_list=None):
        """
        Handle mpirun mode:
          - continue with reduced set of commandline options
          - These options are the keys of opts_to_remove.
          - The values of opts_to_remove are the number of arguments of these options, that also need to be removed.
        """

        if options_list is None:
            options_list = self.default_parseoptions()

        newopts = options_list[:]  # copy
        if self.mpirunmode:
            opts_to_remove = {
                '-np': 1,
                '-machinefile': 1
            }

            for opt in opts_to_remove.keys():
                try:
                    pos = newopts.index(opt)
                    # remove 1 + args
                    del newopts[pos:pos + 1 + opts_to_remove[opt]]
                except ValueError:
                    continue

        GeneralOption.parseoptions(self, newopts)

        # set error logging to file as soon as possible
        if self.options.logtofile:
            print("logtofile %s" % self.options.logtofile)
            if os.path.exists(self.options.logtofile):
                os.remove(self.options.logtofile)
            fancylogger.logToFile(self.options.logtofile)
            fancylogger.logToScreen(False)

    def postprocess(self):
        """Some additional processing"""

        if self.options.debugmpi:
            # set some
            self.options.debug = True
            self.options.debuglvl = 50
            if self.options.stats < 1:
                self.options.stats = 2
            self.options.mpdbootverbose = True

        self.log.debug("final options: %s", self.options)
