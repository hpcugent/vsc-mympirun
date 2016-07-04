#
# Copyright 2009-2016 Ghent University
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

import sys
from vsc.mympirun.mpi.mpi import MPI
from vsc.utils.generaloption import GeneralOption
from vsc.utils.fancylogger import getLogger

# introduce usage / -u option. (original has -h for --hybrid)
# TODO: generate real message with possible alias + mention all supported versions


class MympirunParser(GeneralOption.PARSER):

    """Simple class to implement other help messages"""
    shorthelp = ('u', '--shorthelp', '--usage',)
    longhelp = ('U', '--help',)


class MympirunOption(GeneralOption):
    PARSER = MympirunParser
    ALLOPTSMANDATORY = False  # eg scriptname and other options. same for mpirun options
    INTERSPERSED = False  # Stop parsing cmdline, all others opts are opts for the exe

    def __init__(self, ismpirun=False):
        _logger = getLogger()
        _logger.info("option.py - initializing MympirunOption")

        self.mpirunmode = ismpirun

        # super(MympirunOption, self).__init__()
        GeneralOption.__init__(self)

    def make_init(self):
        _logger = getLogger()
        _logger.info("option.py - initializing options")

        # "walltime":("Job walltime in hours", 'float', 'store', 48, 'l'),
        opts = {
            #long option: (description, type, action, default, short option)
            "showmpi": ("Print the known MPI classes and exit", None,
                        "store_true", False, 'm'),

            "setmpi": (("Specify MPI flavor (eg mpich2, openmpi...; will try "
                        " to guess by default)."), "str", "store", None, "M"),

            "debugmpi": ("Enable MPI level debugging", None, "store_true",
                         False),

            "showsched": ("Print the known Sched classes and exit", None,
                          "store_true", False, 's'),

            "setsched": (("Specify scheduler (eg local, pbs...; will try to "
                          "guess by default)."), "str", "store", None, "S"),

            "debuglvl": ("Specify debug level", "int", "store", 0),

            "mpdbootverbose": ("Run verbose mpdboot", None, "store_true",
                               False),

            "stats": ("Set MPI statistics level", "int", "store", 0),

            "hybrid": (("Run in hybrid mode, specify number of processes "
                       "per node."), "int", "store", None, 'h'),

            "double": (("Run double the amount of processes (eg for GAMESS; "
                       "to change multiplier, use --hybrid)"), None,
                       "store_true", False),

            "output": (("filename to write stdout/stderr directly to (instead "
                       "of stdout)"), "str", "store", None),

            "ssh": (("Force ssh for mpd startup (will try to use optimised "
                    " method by default)"), None, "store_false", True),

            "order": (("Reorder the generated nodelist (default: normal. "
                      "supports: sort, random[_<seed>])"), "str", "store",
                      None),

            "basepath": ("Directory (preferably shared) to use for temporary "
                         "mympirun files (default: HOME).", "str", "store",
                         None),
            # legacy naming

            # don't set it by default. It will be set if needed (eg ipath)
            "pinmpi": ("Disable MPI pinning", None, "store_false", None),

            "rdma": ("Force rdma device", None, "store_true", None),

            "socket": ("Force socket device", None, "store_true", None),

            "universe": (("Start only this number of processes instead of all "
                         "(e.g. for MPI_Spawn) Total size of the universe is "
                         "all requested processes.)"), "int", "store", None),

            "overridepin": (("Let mympriun set the affinity (default: "
                            "disabled, left over to MPI implementation). "
                            "Supported types: 'compact','spread','cycle' "
                            "(add 'pin' postfix for single core pinning, "
                            "e.g. 'cyclepin')."), "str", "store", None),

            "variablesprefix": (("Comma-separated list of exact names or "
                                "prefixes to match environment variables "
                                "(<prefix>_ should match) to pass through."),
                                "string", "extend", []),

            "noenvmodules": ("Don't pass the environment modules variables",
                             None, "store_true", False),

            "mpirunoptions": (("String with options to pass to mpirun (will be "
                              "appended to generate command)"), "str", "store",
                              None),

            'branchcount': ("Set the hydra branchcount", "int", "store", None),

            'qlogic_ipath': ("Force qlogic/true scale ipath", None,
                             "store_true", None),
        }

        descr = ["mympirun options", "General advanced mympirun options"]

        prefix = ''
        self.log.debug("Add mympirun advanced option parser prefix %s descr %s opts %s" % (prefix, descr, opts))
        self.add_group_parser(opts, descr, prefix=prefix)

        # for all MPI classes, get the additional options
        for mpi in MPI.__subclasses__():
            if not mpi.RUNTIMEOPTION is None:
                opts = mpi.RUNTIMEOPTION['options']
                descr = mpi.RUNTIMEOPTION['description']
                prefix = mpi.RUNTIMEOPTION['prefix']
                self.log.debug("Add MPI subclass %s option parser prefix %s descr %s opts %s" %
                               (mpi.__name__, prefix, descr, opts))
                self.add_group_parser(opts, descr, prefix=prefix)

    def parseoptions(self, options_list=None):
        """Handle mpirun mode:
            continue with reduced set of commandline options
            These options are the keys of optsToRemove.
            The values of optsToRemove are the number of arguments of these options, that also need to be removed.
        """

        _logger = getLogger()
        _logger.info("option.py - parseoptions()")


        if options_list is None:
            options_list = self.default_parseoptions()

        newopts = options_list[:]  # copy
        if self.mpirunmode:
            optsToRemove = {'-np': 1,
                            '-machinefile': 1
                            }

            for opt in optsToRemove.keys():
                try:
                    pos = newopts.index(opt)
                    # remove 1 + args
                    del newopts[pos:pos + 1 + optsToRemove[opt]]
                except ValueError:
                    continue

        GeneralOption.parseoptions(self, newopts)

    def postprocess(self):
        """Some additional processing"""

        _logger = getLogger()
        _logger.info("option.py - postprocess()")

        if self.options.debugmpi:
            # set some
            self.options.debug = True
            self.options.debuglvl = 50
            if self.options.stats < 1:
                self.options.stats = 2
            self.options.mpdbootverbose = True
