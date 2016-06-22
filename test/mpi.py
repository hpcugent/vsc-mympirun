#
# Copyright 2012-2016 Ghent University
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
Tests for the vsc.utils.missing module.

@author: Jens Timmerman (Ghent University)
"""
import os
import stat
from unittest import TestCase


from vsc.mympirun.mpi.factory import getinstance
from vsc.mympirun.mpi.mpi import MPI
from vsc.mympirun.rm.local import Local
from vsc.mympirun.option import MympirunOption

# we wish to use the mpirun we ship
os.environ["PATH"] = os.path.dirname(os.path.realpath(__file__)) + os.pathsep + os.environ["PATH"]


class TestMPI(TestCase):
    """Test for the mpi class."""

    def test_MPI_local(self):
        """"Test the MPI class with the local scheduler"""
        # options
        m = MympirunOption()
        m.args = ['echo', 'foo']
        # should not throw an error
        mpi_instance = getinstance(MPI, Local, m)
        mpi_instance.main()

        # check for correct .mpd.conf file
        mpdconffn = os.path.expanduser('~/.mpd.conf')
        perms = stat.S_IMODE(os.stat(mpdconffn).st_mode)
        self.assertEqual(perms, 0400, msg='permissions %0o for mpd.conf %s' % (perms, mpdconffn))

