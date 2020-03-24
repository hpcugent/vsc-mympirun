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
PMI options.
"""
from vsc.mympirun.option import CommonOption
from vsc.mympirun.pmi.mpi import MPI, Tasks

DEFAULT_TIMEOUT = 3600

DISTRIBUTE_PACK = 'pack'
DISTRIBUTE_CYCLE = 'cycle'


class MypmirunOption(CommonOption):
    DESCRIPTION = ["mypmirun options", "General advanced mypmirun options"]
    MPI_CLASS = MPI

    OPTIONS = {
        'pass': (("Passthrough for args to the launcher (leading '--' are prefixed), e.g. "
                  "'--pass=abc=123,def=456' will add '--abc=123 --def=456'. "
                  "It does not support short options or values with a ',' in them."),
                 "strlist", "store", []),
        'print-launcher': ("Generate and print the launcher command", None, "store_true", None),
        'distribute': (("Start ranks in a certain distribution on nodes/sockets/cores: "
                        "%s groups them, %s spreads them") % (DISTRIBUTE_PACK, DISTRIBUTE_CYCLE),
                       None, "store", None, [DISTRIBUTE_PACK, DISTRIBUTE_CYCLE]),
        'all-gpus': ("Each rank sees all (requested) gpus", None, "store_true", None),
    }

    def _modify_base_options(self, base_opts):
        """Hook to modify base options"""
        hybrid_help = ("Run in hybrid mode, specify number of processes per node. "
                       "When GPUs are present, the number of GPUs becomes the default.")
        base_opts['hybrid'] = tuple([hybrid_help] + list(base_opts['hybrid'][1:]))
        return base_opts


class TasksOption(MypmirunOption):
    DESCRIPTION = ["mytasks options", "General advanced mytasks options"]
    MPI_CLASS = Tasks

    def _modify_base_options(self, base_opts):
        """Remove some mympirun specific options"""
        base_opts = super(TasksOption, self)._modify_base_options(base_opts)
        for longopt in ['showsched', 'setsched', 'showmpi', 'setmpi']:
            del base_opts[longopt]

        return base_opts
