#!/usr/bin/env python
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
A mpirun wrapper

v1 bash 10/08/2009
v2 python rewrite 19/03/2010
v3 refactored python 28/08/2012
v4 cleanup 5/11/2013

@author: Stijn De Weirdt
@author: Jens Timmerman
@author: Jeroen De Clerck
"""

import os
import pkgutil
import sys

import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.option import MympirunOption
from vsc.mympirun.factory import getinstance
import vsc.mympirun.rm.sched as schedm
from vsc.utils import fancylogger


def get_mpi_and_sched_and_options():
    """
    Selects mpi flavor and scheduler based on environment and arguments.

    @return: A triplet containing the chosen mpi flavor, chosen scheduler and the MympirunOption class.
    """

    # import all modules in this dir: http://stackoverflow.com/a/16853487
    for loader, modulename, _ in pkgutil.walk_packages([os.path.dirname(schedm.__file__),
                                                        os.path.dirname(mpim.__file__)]):
        loader.find_module(modulename).load_module(modulename)

    scriptname = os.path.basename(os.path.abspath(sys.argv[0]))
    # if the scriptname is 'mpirun', its means that mympirun was called through the faked mpirun path
    isfake = scriptname == 'mpirun'

    # init generaloption with the various mpirun cli options
    optionparser = MympirunOption(ismpirun=isfake)

    # see if an mpi flavor was explicitly chosen as a command line argument. If not, just use the mpirun that was called
    # We are using sys.argv because generaloption depends on the the returned scriptname
    if optionparser.options.setmpi:
        setmpi = optionparser.options.setmpi
        optionparser.log.debug("mympirun has been forced to use %s as MPI flavor", setmpi)
    else:
        setmpi = sys.argv[0]
        optionparser.log.debug("mympirun will be executed by %s", setmpi)

    scriptname, mpi, found_mpi = mpim.what_mpi(setmpi)
    optionparser.log.debug("Found MPI classes %s", found_mpi)
    found_mpi_names = [x.__name__ for x in found_mpi]

    if optionparser.options.showmpi:
        fancylogger.setLogLevelInfo()
        optionparser.log.info("Found MPI classes %s", ", ".join(found_mpi_names))
        return None

    # Select a Scheduler from the available schedulers
    sched, found_sched = schedm.what_sched(getattr(optionparser.options, 'schedtype', None))
    optionparser.log.debug("Found Sched classes %s", found_sched)
    found_sched_names = [x.__name__ for x in found_sched]

    if optionparser.options.showsched:
        fancylogger.setLogLevelInfo()
        optionparser.log.info("Found Sched classes %s", ", ".join(found_sched_names))
        return None

    if mpi is None:
        optionparser.log.raiseException(("No MPI class found that supports scriptname %s; isfake %s). Please use "
                                         "mympirun through one of the direct calls or make sure the mpirun command can"
                                         " be found. Found MPI %s") %
                                        (scriptname, isfake, ", ".join(found_mpi_names)))
    else:
        optionparser.log.debug("Found MPI class %s (scriptname %s; isfake %s)", mpi.__name__, scriptname, isfake)

    if sched is None:
        optionparser.log.raiseException("No sched class found (options.schedtype %s ; found Sched classes %s)",
                                        optionparser.options.schedtype, ", ".join(found_sched_names))
    else:
        optionparser.log.debug("Found sched class %s from options.schedtype %s (all Sched found %s)",
                               sched.__name__, optionparser.options.schedtype, ", ".join(found_sched_names))

    if not optionparser.args:
        optionparser.log.warn("no mpi script provided")
        return None

    return mpi, sched, optionparser


def main():
    """Main function"""
    try:
        instance_options = get_mpi_and_sched_and_options()
        if instance_options:
            instance = getinstance(*instance_options)
            instance.main()
    except Exception:
        fancylogger.getLogger().exception("Main failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
