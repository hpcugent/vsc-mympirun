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
import unittest
import re
import string

from vsc.utils.fancylogger import getLogger
from vsc.utils.run import run_simple
from vsc.mympirun.factory import getinstance
import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.mpi.openmpi import OpenMPI
from vsc.mympirun.mpi.intelmpi import IntelMPI
from vsc.mympirun.mpi.mpich import MPICH2
from vsc.mympirun.rm.local import Local
from vsc.mympirun.option import MympirunOption

# we wish to use the mpirun we ship
os.environ["PATH"] = os.path.dirname(os.path.realpath(__file__)) + os.pathsep + os.environ["PATH"]

LOGGER = getLogger()


class TestMPI(unittest.TestCase):

    """tests for vsc.mympirun.mpi.mpi functions"""

    #######################
    ## General functions ##
    #######################

    def test_what_mpi(self):
        """test if what_mpi returns the correct mpi flavor"""
        scriptnames = ["ompirun", "mpirun", "impirun", "mympirun"]
        for scriptname in scriptnames:
            # if the scriptname is an executable located on this machine
            if mpim.which(scriptname):
                (returned_scriptname, mpi, found) = mpim.what_mpi(scriptname)
                LOGGER.debug("%s, %s, %s", returned_scriptname, mpi, found)
                # if an mpi implementation was found
                if mpi:
                    self.assertTrue(mpi in found)
                    self.assertTrue(returned_scriptname == scriptname)
                else:
                    self.assertTrue(returned_scriptname.endswith("mpirun"), "")

    def test_stripfake(self):
        """Test if stripfake actually removes the /bin/fake path in $PATH"""
        LOGGER.debug("old path: %s", os.environ["PATH"])
        mpim.stripfake()
        newpath = os.environ["PATH"]
        self.assertFalse(("bin/%s" % mpim.FAKE_SUBDIRECTORY_NAME) in newpath)

    def test_which(self):
        """test if which returns a path that corresponds to unix which"""
        scriptnames = ["ompirun", "mpirun", "impirun", "mympirun"]
        for scriptname in scriptnames:
            mpimwhich = mpim.which(scriptname) + "\n"
            exitcode, unixwhich = run_simple("which " + scriptname)
            if exitcode > 0:
                LOGGER.raiseException("Something went wrong while trying to run `which`")
            self.assertEqual(mpimwhich, unixwhich, msg=("the return values of unix which and which() aren't the same: "
                                                        "%s != %s") % (mpimwhich, unixwhich))

    ###################
    ## MPI functions ##
    ###################

    def test_options(self):
        """running mympirun with bad options"""
        optionparser = MympirunOption()
        optionparser.args = ['echo', 'foo']
        # should not throw an error
        try:
            mpi_instance = getinstance(mpim.MPI, Local, optionparser)
            mpi_instance.main()
        except Exception:
            self.fail("mympirun raised an exception while running main()")

        optdict = mpi_instance.options

        # why isnt this a dict??
        LOGGER.debug("MPI INSTANCE OPTIONS: %s, type %s", optdict, type(optdict))

        # for opt in m.args:
        #    self.assertFalse(opt in mpi_instance.options)

    def test_is_mpirun_for(self):
        """test if _is_mpirun_for returns true when it is given the path of its executable"""
        optionparser = MympirunOption()
        implementations = [OpenMPI, IntelMPI, MPICH2]
        for implementation in implementations:
            instance = getinstance(implementation, Local, optionparser)
            # only works with modules
            # self.assertTrue(instance._is_mpirun_for(mpim.which(instance._mpiscriptname_for[0])), msg="")

    def test_set_omp_threads(self):
        """test if OMP_NUM_THREAD gets set correctly"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.set_omp_threads()
        self.assertTrue(getattr(mpi_instance.options, 'ompthreads', None) is not None)
        self.assertEqual(os.environ["OMP_NUM_THREADS"], getattr(mpi_instance.options, 'ompthreads', None))

    def test_set_netmask(self):
        """test if netmask matches the layout of an ip adress"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.set_netmask()
        # matches "IP address / netmask"
        reg = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        for substr in string.split(mpi_instance.netmask, sep=":"):
            self.assertTrue(reg.match(substr))

    def test_select_device(self):
        """test if device and netmasktype are set and are picked from a list of options"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.select_device()
        self.assertTrue(mpi_instance.device and mpi_instance.device in mpi_instance.DEVICE_MPIDEVICE_MAP.values())
        self.assertTrue(mpi_instance.netmasktype and mpi_instance.netmasktype in mpi_instance.NETMASK_TYPE_MAP.values())

    def test_make_node_file(self):
        """test if the nodefile is made and if it contains the same amount of nodas as mpinodes"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.make_node_file()
        self.assertTrue(os.path.isfile(mpi_instance.mpiexec_node_filename))

        # test if amount of lines in nodefile matches amount of nodes
        with open(mpi_instance.mpiexec_node_filename) as file:
            index = 0
            for index, _ in enumerate(file):
                pass
            self.assertEqual(len(mpi_instance.mpinodes), index+1)

    def test_make_mympirundir(self):
        """test if the mympirundir is made"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.make_mympirundir()
        self.assertTrue(mpi_instance.mympirundir and os.path.isdir(mpi_instance.mympirundir))

    def test_make_mpdboot(self):
        """test if the mpdboot conffile is made and has the correct permissions"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.make_mpdboot()
        mpdconffn = os.path.expanduser('~/.mpd.conf')
        self.assertTrue(os.path.exists(mpdconffn))
        perms = stat.S_IMODE(os.stat(mpdconffn).st_mode)
        self.assertEqual(perms, stat.S_IREAD, msg='permissions %0o for mpd.conf %s' % (perms, mpdconffn))

    def test_set_mpdboot_localhost_interface(self):
        """test if mpdboot_localhost_interface is set correctly"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        mpi_instance.set_mpdboot_localhost_interface()
        (nodename, iface) = mpi_instance.mpdboot_localhost_interface
        self.assertTrue(mpi_instance.mpdboot_localhost_interface and nodename and iface)
        self.assertTrue((nodename, iface) in mpi_instance.get_localhosts())

    def test_get_localhosts(self):
        """test if localhost returns a list containing that are sourced correctly"""
        optionparser = MympirunOption()
        mpi_instance = getinstance(mpim.MPI, Local, optionparser)
        res = mpi_instance.get_localhosts()
        _, out = run_simple("/sbin/ip -4 -o addr show")
        for (nodename, interface) in res:
            self.assertTrue(nodename in mpi_instance.uniquenodes)
            self.assertTrue(interface in out)
