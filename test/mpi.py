#!/usr/bin/env python
##
#
# Copyright 2012-2013 Ghent University
#
# This file is part of vsc-ldap,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/vsc-ldap
#
# vsc-ldap is free software: you can redistribute it and/or modify
# it under the terms of the GNU Library General Public License as
# published by the Free Software Foundation, either version 2 of
# the License, or (at your option) any later version.
#
# vsc-ldap is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with vsc-ldap. If not, see <http://www.gnu.org/licenses/>.
##
"""
Tests for the vsc.utils.missing module.

@author: Jens Timmerman (Ghent University)
"""
import os
import stat
from unittest import TestCase, TestLoader


from vsc.mympirun.mpi.factory import getinstance
from vsc.mympirun.mpi.mpi import MPI
from vsc.mympirun.rm.local import Local
from vsc.mympirun.option import MympirunOption

# we wish to use the mpirun we ship
os.environ["PATH"] += os.pathsep + os.path.realpath(__file__)


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
        self.assertEqual(stat.S_IMODE(os.stat(mpdconffn).st_mode), 0400)


def suite():
    """ return all the tests"""
    return TestLoader().loadTestsFromTestCase(TestMPI)
