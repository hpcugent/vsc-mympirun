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
from vsc.mympirun.option import CommonOption
from vsc.mympirun.mpi.mpi import MPI, TIMEOUT_CODE

DEFAULT_TIMEOUT = 3600


class MympirunOption(CommonOption):
    DESCRIPTION = ["mympirun options", "General advanced mympirun options"]
    MPI_CLASS = MPI
    OPTIONS = {
        # long option: (description, type, action, default, short option)
        "basepath": ("Directory (preferably shared) to use for temporary mympirun files (default: HOME).",
                     "str", "store", None),

        'branchcount': ("Set the hydra branchcount", "int", "store", None),

        "double": ("Run double the amount of processes (equivalent to --multi 2)", None, "store_true", False),

        "launcher": ("The launcher to be used by Hydra (used in recent Intel MPI versions (> 4.1))"
                     "for example: ssh, pbsdsh, ..", "str", "store", None),

        "mpdbootverbose": ("Run verbose mpdboot", None, "store_true", False),

        "mpirunoptions": ("String with options to pass to mpirun (will be appended to generate command)",
                          "str", "store", None),

        "noenvmodules": ("Don't pass the environment modules variables", None, "store_true", False),

        "order": ("Reorder the generated nodelist (default: normal. supports: sort, random[_<seed>])",
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

        "sockets-per-node": ("Number of sockets per node (default: 0, i.e. try to detect #sockets "
                             "from /proc/cpuinfo)", "int", "store", 0),

        "ssh": ("Force ssh for mpd startup (will try to use optimised method by default)",
                None, "store_false", True),

        'use_psm': ("Use Performance Scaled Messaging", None, "store_true", None),

        "universe": (("Start only this number of processes instead of all (e.g. for MPI_Spawn) Total size of the "
                      "universe is all requested processes.)"), "int", "store", None),

        "variablesprefix": (("Comma-separated list of exact names or prefixes to match environment variables "
                             "(<prefix>_ should match) to pass through."), "string", "extend", [], 'V'),

    }

    def _modify_base_options(self, base_opts):
        """Hook to modify base options"""
        # legacy naming
        base_opts['schedtype'] = base_opts.pop('setsched')
        return base_opts
