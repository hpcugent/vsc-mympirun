#!/usr/bin/env python
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
An srun based non-mpi multi process wrapper
"""

import sys
from vsc.utils import fancylogger

from vsc.mympirun.factory import getinstance
from vsc.mympirun.pmi.mpi import Tasks as mpi
from vsc.mympirun.pmi.slurm import Tasks as sched
from vsc.mympirun.pmi.option import TasksOption


def main():
    try:
        optionparser = TasksOption(ismpirun=False)
        instance = getinstance(mpi, sched, optionparser)
        instance.main()
    except Exception:
        fancylogger.getLogger().exception("Main failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
