#
# Copyright 2011-2019 Ghent University
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

from vsc.utils import fancylogger


_coupler_class_cache = {}


_log = fancylogger.getLogger('mympirun.factory', fname=False)


def getinstance(mpi, sched, options):
    """
    Make an instance of the relevant MPI class. Also set the RM instance

    @param mpi: a class subclassing from MPI (e.g. returned by whatMPI)
    @param sched: a class subclassing from sched (e.g. returned by whatSched)
    @param options: an instance of MympirunOption

    @return: an instance that is a subclass of the selected MPI and Scheduler
    """
    cache_key = (mpi, sched)

    if cache_key not in _coupler_class_cache:
        class Coupler(mpi, sched):
            """Temporary class to couple MPI and local sched"""
            def __init__(self, **kwargs):
                self.log = fancylogger.getLogger("%s_%s" % (mpi.__name__, sched.__name__))
                super(Coupler, self).__init__(**kwargs)

        _coupler_class_cache[cache_key] = Coupler
        _log.debug("Created new 'Coupler' class for %s: %s", cache_key, id(Coupler))

    coupler_class = _coupler_class_cache[cache_key]
    _log.debug("Fetched Coupler class from cache %s: %s", cache_key, id(coupler_class))

    return coupler_class(options=options.options, cmdargs=options.args)
