#
# Copyright 2009-2019 Ghent University
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
import os

from vsc.mympirun.mpi.mpi import MPI, TIMEOUT_CODE
from vsc.utils import fancylogger
from vsc.utils.generaloption import GeneralOption
from vsc.utils.missing import get_subclasses
# introduce usage / -u option. (original has -h for --hybrid)

DEFAULT_TIMEOUT = 3600

class MympirunParser(GeneralOption.PARSER):

    """Simple class to implement other help messages"""
    shorthelp = ('u', '--shorthelp', '--usage',)
    longhelp = ('U', '--help',)


class MympirunOption(GeneralOption):
    """
    Class that extends vsc-utils.GeneralOption

    Parses commandline options and sets them to variables
    """
    PARSER = MympirunParser
    ALLOPTSMANDATORY = False  # eg scriptname and other options. same for mpirun options
    INTERSPERSED = False  # Stop parsing cmdline, all others opts are opts for the exe

    def __init__(self, ismpirun=False):
        self.mpirunmode = ismpirun

        GeneralOption.__init__(self)

    def make_init(self):
        """ add all the options to generaloption, so it can correctly parse the command line arguments """

        opts = {
            # long option: (description, type, action, default, short option)

            "basepath": ("Directory (preferably shared) to use for temporary mympirun files (default: HOME).",
                         "str", "store", None),

            'branchcount': ("Set the hydra branchcount", "int", "store", None),

            "debuglvl": ("Specify debug level", "int", "store", 0),

            "debugmpi": ("Enable MPI level debugging", None, "store_true", False),

            "dry-run": ("Dry run mode, just print command that will be executed", None, 'store_true', False, 'D'),

            "double": ("Run double the amount of processes (equivalent to --multi 2)", None, "store_true", False),

            "hybrid": ("Run in hybrid mode, specify number of processes per node.", "int", "store", None, 'h'),

            "launcher": ("The launcher to be used by Hydra (used in recent Intel MPI versions (> 4.1))"
                         "for example: ssh, pbsdsh, ..", "str", "store", None),

            "logtofile": ("redirect the logging of mympirun to a file (instead of stdout/stderr)",
                          "str", "store", None),

            "mpdbootverbose": ("Run verbose mpdboot", None, "store_true", False),

            "mpirunoptions": ("String with options to pass to mpirun (will be appended to generate command)",
                              "str", "store", None),

            "multi": ("Run the amount of processes multiplied by the given integer", "int", "store", None),

            "noenvmodules": ("Don't pass the environment modules variables",
                             None, "store_true", False),

            "order": ("Reorder the generated nodelist (default: normal. supports: sort, random[_<seed>])",
                      "str", "store", None),

            "output": ("redirect the output of mpirun to a file (instead of stdout/stderr)",
                       "str", "store", None),

            "output-check-timeout": ("Warn when no stdout/stderr was seen after start (in seconds; negative number "
                                     "disables this test", "int", "store", DEFAULT_TIMEOUT),

            "output-check-fatal": ("Exit with code %s instead of warn in case of output check timeout" % TIMEOUT_CODE,
                                    None, "store_true", False),

            "overridepin": (("Let mympriun set the affinity (default: disabled, left over to MPI implementation). "
                             "Supported types: 'compact','spread','cycle' (add 'pin' postfix for single core pinning, "
                             "e.g. 'cyclepin')."), "str", "store", None),

            # don't set it by default. It will be set if needed (eg ipath)
            "pinmpi": ("Disable MPI pinning", None, "store_true", True),

            "rdma": ("Force rdma device", None, "store_true", None),

            "schedtype": ("Specify scheduler (eg local, pbs...; will try to guess by default).",
                      "str", "store", None, "S"),

            "setmpi": ("Specify MPI flavor (eg mpich2, openmpi...; will try to guess by default).",
                       "str", "store", None, "M"),

            "showmpi": ("Print the known MPI classes and exit", None, "store_true", False, 'm'),

            "showsched": ("Print the known Sched classes and exit", None, "store_true", False, 's'),

            "sockets-per-node": ("Number of sockets per node (default: 0, i.e. try to detect #sockets "
                                 "from /proc/cpuinfo)", "int", "store", 0),

            "ssh": ("Force ssh for mpd startup (will try to use optimised method by default)",
                    None, "store_false", True),

            "stats": ("Set MPI statistics level", "int", "store", 0),

            "universe": (("Start only this number of processes instead of all (e.g. for MPI_Spawn) Total size of the "
                          "universe is all requested processes.)"), "int", "store", None),

            'use_psm': ("Use Performance Scaled Messaging", None, "store_true", None),

            "variablesprefix": (("Comma-separated list of exact names or prefixes to match environment variables "
                                 "(<prefix>_ should match) to pass through."), "string", "extend", []),

        }

        descr = ["mympirun options", "General advanced mympirun options"]

        prefix = ''
        self.log.debug("Add advanced option parser: options %s, description %s, prefix %s", opts, descr, prefix)
        self.add_group_parser(opts, descr, prefix=prefix)

        # for all MPI classes, get the additional options
        for mpi in get_subclasses(MPI):
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
