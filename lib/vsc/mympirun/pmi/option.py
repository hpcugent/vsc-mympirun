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
PMI options.
"""
from vsc.mympirun.option import CommonOption
from vsc.mympirun.pmi.mpi import MPI

DEFAULT_TIMEOUT = 3600


class MympirunOption(CommonOption):
    DESCRIPTION = ["mypmirun options", "General advanced mypmirun options"]
    MPI_CLASS = MPI

    OPTIONS = {
        'pass': (("Passthrough for args to the launcher (leading '--' are prefixed), e.g. "
                  "'--pass=abc=123,def=456' will add '--abc=123 --def=456'. "
                  "It does not support short options or values with a ',' in them."),
                 "strlist", "store", []),
    }
