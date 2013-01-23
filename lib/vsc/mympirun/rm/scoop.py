# #
# Copyright 2009-2013 Ghent University
# Copyright 2009-2013 Stijn De Weirdt
#
# This file is part of VSC-tools,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/VSC-tools
#
# VSC-tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# VSC-tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VSC-tools. If not, see <http://www.gnu.org/licenses/>.
# #

"""
Local scheduler : no scheduler, act on single node
"""

from vsc.mympirun.rm.local import Local

class Scoop(Local):
    """
    Class for jobs running on localhost started by SCOOP (ie no scheduler settings)
    - will use the amount of cores found on localhost.
    """
    _sched_for = ['scoop']
    SCHED_ENVIRON_ID = 'SCOOP_JOBID'  # with Local, this is optional

