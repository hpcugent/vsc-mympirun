#!/usr/bin/env python
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
A mpirun wrapper

v1 bash 10/08/2009
v2 python rewrite 19/03/2010
v3 refactored python 28/08/2012
v4 cleanup 5/11/2013

TODO:
    intel tuning code

@author: Stijn De Weirdt
@author: Jens Timmerman
@author: Jeroen De Clerck
"""

import glob
import inspect
import os
import sys
import traceback

import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.option import MympirunOption
from vsc.mympirun.rm.factory import getinstance
import vsc.mympirun.rm.sched as schedm
from vsc.utils import fancylogger

_logger = fancylogger.getLogger()
fancylogger.setLogLevelDebug()

def get_mpi_and_sched_and_options():
    """
    selects mpi flavor and scheduler based on environment and arguments

    @return: A triplet containing the chosen mpi flavor, chosen scheduler and the MympirunOption class.
    """

    scriptname = os.path.basename(os.path.abspath(sys.argv[0]))
    isfake = scriptname == 'mpirun'

    # init generaloption with the various mpirun cli options
    mo = MympirunOption(ismpirun=isfake)

    # see if an mpi flaver was explicitly chosen as an argument
    # if not, just use the mpirun that was called
    # We are using sys.argv because generaloption depends on the the returned
    # scriptname
    setmpi = mo.options.setmpi if mo.options.setmpi else sys.argv[0]
    _logger.debug("User chose MPI flavor: %s" % setmpi)
    scriptname, mpi, found_mpi = mpim.whatMPI(setmpi)

    if mo.args is None or len(mo.args) == 0:
        mo.parser.print_shorthelp()
        _logger.warn("no arguments provided, exiting")
        sys.exit(0)

    # Select a Scheduler from the available schedulers
    sched, found_sched = schedm.whatSched(getattr(mo.options, 'setsched', None))

    found_mpi_names = [x.__name__ for x in found_mpi]
    found_sched_names = [x.__name__ for x in found_sched]

    if mo.options.showmpi:
        fancylogger.setLogLevelInfo()
        _logger.info("Found MPI classes %s" %
            (", ".join(found_mpi_names)))
        sys.exit(0)

    if mo.options.showsched:
        fancylogger.setLogLevelInfo()
        _logger.info("Found Sched classes %s" %
            (", ".join(found_sched_names)))
        sys.exit(0)

    if mpi is None:
        mo.log.raiseException(
            ("No MPI class found that supports scriptname %s; isfake %s). "
             "Please use mympirun through one of the direct calls or make sure "
             "the mpirun command can be found. Found MPI %s") %
            (scriptname, isfake, ", ".join(found_mpi_names)))
    else:
        mo.log.debug("Found MPI class %s (scriptname %s; isfake %s)" %
                     (mpi.__name__, scriptname, isfake))

    if sched is None:
        mo.log.raiseException(
            ("No sched class found (options.setsched %s ; found Sched "
             "classes %s)") % (mo.options.setsched,
             ", ".join(found_sched_names)))
    else:
        mo.log.debug(
            ("Found sched class %s from options.setsched %s (all Sched "
             "found %s)") % (sched.__name__, mo.options.setsched,
             ", ".join(found_sched_names)))

    return mpi, sched, mo

def main():
    """Main function"""
    try:
        m = getinstance(*get_mpi_and_sched_and_options())
        m.main()
    except Exception:
        _logger.exception("Main failed; Trace: \n %s", traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
