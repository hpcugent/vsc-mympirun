#
# Copyright 2011-2023 Ghent University
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
Factory for MPI instance, this will return a instance based on the given
mpi and scheduler class

@author: Stijn De Weirdt, Jens Timmerman
"""
import logging


_coupler_class_cache = {}


def getinstance(mpi, sched, options):
    """
    Make an instance of the relevant MPI class. Also set the RM instance

    @param mpi: a class subclassing from MPI (e.g. returned by whatMPI)
    @param sched: a class subclassing from sched (e.g. returned by whatSched)
    @param options: an instance of MympirunOption

    @return: an instance that is a subclass of the selected MPI and Scheduler
    """
    base_classes = (mpi, sched)

    if base_classes not in _coupler_class_cache:
        coupler_class = type(
            "Coupler_%s_%s" % (mpi.__name__, sched.__name__),
            base_classes,
            {
                'HIDDEN': True,
            }
        )
        _coupler_class_cache[base_classes] = coupler_class
        tmpl = "Created new Coupler %s class for %s: %s"
    else:
        tmpl = "Fetched Coupler class %s from cache %s: %s"
        coupler_class = _coupler_class_cache[base_classes]

    logging.debug(tmpl, base_classes, coupler_class.__name__, id(coupler_class))
    return coupler_class(options=options.options, cmdargs=options.args)
