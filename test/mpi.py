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
from random import choice
from string import ascii_uppercase

from vsc.utils.fancylogger import getLogger
from vsc.mympirun.rm.factory import getinstance
import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.rm.local import Local
from vsc.mympirun.option import MympirunOption

# we wish to use the mpirun we ship
os.environ["PATH"] = os.path.dirname(os.path.realpath(__file__)) + os.pathsep + os.environ["PATH"]


_logger = getLogger()


class TestMPI(TestCase):

    """Test for the mpi class."""

    def test_whatMPI(self):
        scriptnames = ["ompirun", "mpirun", "impirun", "mympirun"]
        for scriptname in scriptnames:
            # if the scriptname is an executable located on this machine
            if mpim.which(scriptname):
                (returned_scriptname, mpi, found) = mpim.whatMPI(scriptname)
                _logger.debug("%s, %s, %s", returned_scriptname, mpi, found)
                # if an mpi implementation was found
                if mpi:
                    self.assertTrue(mpi in found)
                    self.assertTrue(returned_scriptname == scriptname)
                else:
                    self.assertEqual(returned_scriptname, "mpirun")

    def test_stripfake(self):

        # path_to_append is a string
        oldpath = os.environ["PATH"]
        append = ''.join(choice(ascii_uppercase) for i in range(12))
        _logger.debug("oldpath: %s", oldpath)

        res = mpim.stripfake(path_to_append=append)
        newpath = os.environ["PATH"]
        self.assertEqual(res, newpath.split(os.pathsep),
                         msg=("stripfake returned string doesn't correspond to the current $PATH: "
                              "res = %s and path = %s") % (res, newpath))
        self.assertTrue(append in newpath,
                        msg=("old $PATH was %s, new $PATH "
                             "is %s, path_to_append was %s") % (oldpath, newpath, append))

        self.assertFalse(("bin/%s" % mpim.FAKE_SUBDIRECTORY_NAME) in newpath)

        # path_to_append is a list
        append = [append]
        append.append(''.join(choice(ascii_uppercase) for i in range(12)))
        append.append(''.join(choice(ascii_uppercase) for i in range(12)))

        res = mpim.stripfake(path_to_append=append)
        newpath = os.environ["PATH"]
        self.assertEqual(res, newpath.split(os.pathsep),
                         msg=("stripfake returned string doesn't correspond to the current $PATH: "
                              "res = %s and path = %s") % (res, newpath))
        for p in append:
            self.assertTrue(p in newpath,
                            msg="old $PATH was %s, new $PATH is %s, path_to_append was %s" %
                                (oldpath, newpath, p))

        self.assertFalse(("bin/%s" % mpim.FAKE_SUBDIRECTORY_NAME) in newpath)

    def test_which(self):
        pass

    def test_options(self):
        """Bad options"""
        m = MympirunOption()
        m.args = ['echo', 'foo']
        # should not throw an error
        try:
            mpi_instance = getinstance(mpim.MPI, Local, m)
            mpi_instance.main()
        except Exception:
            self.fail("mympirun raised an exception")

        optdict = mpi_instance.options

        # why isnt this a dict??
        _logger.debug("MPI INSTANCE OPTIONS: %s, type %s", optdict, type(optdict))

        # for opt in m.args:
        #    self.assertFalse(opt in mpi_instance.options)

    def test_MPI_local(self):
        """"Test the MPI class with the local scheduler"""
        # options
        m = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, m)
        mpi_instance.main()

        # check for correct .mpd.conf file
        mpdconffn = os.path.expanduser('~/.mpd.conf')
        perms = stat.S_IMODE(os.stat(mpdconffn).st_mode)
        self.assertEqual(perms, 0400, msg='permissions %0o for mpd.conf %s' % (perms, mpdconffn))
