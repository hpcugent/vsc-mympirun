#
# Copyright 2012-2017 Ghent University
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
Tests for the vsc.mympirun.mpi.mpi module.

@author: Jeroen De Clerck
@author: Kenneth Hoste (HPC-UGent)
"""
from IPy import IP
import os
import pkgutil
import re
import shutil
import stat
import string
import tempfile
import unittest
from vsc.install.testing import TestCase
from vsc.utils.run import run
from vsc.utils.missing import get_subclasses, nub

from vsc.mympirun.factory import getinstance
import vsc.mympirun.mpi.mpi as mpim
from vsc.mympirun.mpi.openmpi import OpenMPI, OpenMpiOversubscribe
from vsc.mympirun.mpi.intelmpi import IntelMPI, IntelHydraMPIPbsdsh
from vsc.mympirun.option import MympirunOption
from vsc.mympirun.rm.local import Local

from sched import reset_env

# we wish to use the mpirun we ship
os.environ["PATH"] = os.path.dirname(os.path.realpath(__file__)) + os.pathsep + os.environ["PATH"]


class TestMPI(TestCase):

    """tests for vsc.mympirun.mpi.mpi functions"""

    def setUp(self):
        self.orig_environ = os.environ
        self.tmpdir = tempfile.mkdtemp()
        os.environ['HOME'] = self.tmpdir

    def tearDown(self):
        """Clean up after running test."""
        reset_env(self.orig_environ)
        shutil.rmtree(self.tmpdir)

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
                print("what mpi returns: %s, %s, %s" % (returned_scriptname, mpi, found))
                # if an mpi implementation was found
                if mpi:
                    self.assertTrue(mpi in found,
                                    msg="returned mpi (%s) is not an element of found_mpi (%s)" % (mpi, found))
                    self.assertTrue(returned_scriptname == scriptname,
                                    msg="returned scriptname (%s) doesn't match actual scriptname (%s)" %
                                    (returned_scriptname, scriptname))
                else:
                    self.assertTrue(returned_scriptname.endswith("mpirun") or returned_scriptname is None,
                                    msg="no mpi found, scriptname should be the path to mpirun or None, but is %s" %
                                    returned_scriptname)

    def test_stripfake(self):
        """Test if stripfake actually removes the /bin/fake path in $PATH"""
        print("old path: %s" % os.environ["PATH"])
        mpim.stripfake()
        newpath = os.environ["PATH"]
        self.assertFalse(("bin/%s/mpirun" % mpim.FAKE_SUBDIRECTORY_NAME) in newpath, msg="the faked dir is still in $PATH")

    def test_which(self):
        """test if which returns a path that corresponds to unix which"""

        testnames = ["python", "head", "tail", "cat"]

        for scriptname in testnames:
            mpiwhich = mpim.which(scriptname)
            exitcode, unixwhich = run("which " + scriptname)
            if exitcode > 0:
                raise Exception("Something went wrong while trying to run `which`: %s" % unixwhich)

            self.assertTrue(mpiwhich, msg="mpi which did not return anything, (unix which: %s" % unixwhich)
            self.assertEqual(mpiwhich, string.strip(unixwhich),
                             msg="the return values of unix which and which() aren't"" the same: %s != %s" %
                             (mpiwhich, string.strip(unixwhich)))

     ###################
     ## MPI functions ##
     ###################

    def test_options(self):
        """running mympirun with bad options"""
        optionparser = MympirunOption()
        optionparser.args = ['echo', 'foo', 'zever']
        # should not throw an error
        try:
            mpi_instance = getinstance(mpim.MPI, Local, optionparser)
            mpi_instance.main()
        except Exception:
            self.fail("mympirun raised an exception while running main()")

        optdict = mpi_instance.options.__dict__

        print("args given to mympirunoption: %s, instance options: %s, " % (optionparser.args, optdict))

        for opt in optionparser.args:
            self.assertFalse(opt in optdict)

    def test_is_mpirun_for(self):
        """test if _is_mpirun_for returns true when it is given the path of its executable"""
        impi_instance = getinstance(IntelMPI, Local, MympirunOption())

        fake_mpirun_path = os.path.join('/tmp/test/bin/intel64/mpirun')

        # $EBROOT* not set
        self.assertFalse(impi_instance._is_mpirun_for(fake_mpirun_path))

        # other $EBROOT* value
        os.environ['EBROOTIMPI'] = '/tmp/foo/bar'
        self.assertFalse(impi_instance._is_mpirun_for(fake_mpirun_path))

        os.environ['EBROOTIMPI'] = '/tmp/test'

        # $EBVERSION* not set
        self.assertFalse(impi_instance._is_mpirun_for(fake_mpirun_path))
        os.environ['EBVERSIONIMPI'] = '4.0.1'
        self.assertTrue(impi_instance._is_mpirun_for(fake_mpirun_path))
        os.environ['EBVERSIONIMPI'] = '5.1.3'
        self.assertFalse(impi_instance._is_mpirun_for(fake_mpirun_path))

        impi_instance = getinstance(IntelHydraMPIPbsdsh, Local, MympirunOption())
        self.assertTrue(impi_instance._is_mpirun_for(fake_mpirun_path))

    def test_set_omp_threads(self):
        """test if OMP_NUM_THREAD gets set correctly"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.set_omp_threads()
        self.assertTrue(getattr(mpi_instance.options, 'ompthreads') is not None, msg="ompthreads was not set")
        self.assertEqual(os.environ["OMP_NUM_THREADS"], getattr(mpi_instance.options, 'ompthreads', None),
                         msg="ompthreads has not been set in the environment variable OMP_NUM_THREADS")

    def test_set_netmask(self):
        """test if netmask matches the layout of an ip adress"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.set_netmask()
        # matches "IP address / netmask"
        reg = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        print("netmask: %s" % mpi_instance.netmask)
        for substr in string.split(mpi_instance.netmask, sep=":"):
            try:
                IP(substr)
            except ValueError:
                self.fail()

    def test_select_device(self):
        """test if device and netmasktype are set and are picked from a list of options"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.select_device()
        self.assertTrue(mpi_instance.device and mpi_instance.device in mpi_instance.DEVICE_MPIDEVICE_MAP.values(),
                        msg="%s is not a valid device type, possible values: %s" %
                        (mpi_instance.device, mpi_instance.DEVICE_MPIDEVICE_MAP.values()))
        self.assertTrue(mpi_instance.netmasktype and mpi_instance.netmasktype in mpi_instance.NETMASK_TYPE_MAP.values(),
                        msg="%s is not a valid netmask type, possible values: %s" %
                        (mpi_instance.netmasktype, mpi_instance.NETMASK_TYPE_MAP.values()))

    def test_make_machine_file(self):
        """test if the machinefile is made and if it contains the same amount of nodes as mpinodes"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.make_machine_file()
        self.assertTrue(os.path.isfile(mpi_instance.mpiexec_node_filename), msg="the nodefile has not been created")

        # test if amount of lines in nodefile matches amount of nodes
        with open(mpi_instance.mpiexec_node_filename) as file:
            index = 0
            for index, _ in enumerate(file):
                pass
            self.assertEqual(len(mpi_instance.mpinodes), index+1,
                             msg="mpinodes doesn't match the amount of nodes in the nodefile")

        # disable make_mympirundir
        mpi_instance.make_mympirundir = lambda: True
        mpi_instance.mympirundir = '/does/not/exist/'
        self.assertErrorRegex(IOError, "failed to write nodefile", mpi_instance.make_machine_file)

        # openmpi oversubscribing
        mpi_instance = getinstance(OpenMpiOversubscribe, Local, MympirunOption())
        mpi_instance.options.double = True
        mpi_instance.set_multiplier()
        mpi_instance.make_machine_file()

        with open(mpi_instance.mpiexec_node_filename) as file:
            n_slots = mpi_instance.ppn
            regex = re.compile("slots=%s" % n_slots)
            machinefile = file.read()
            self.assertTrue(regex.search(machinefile), "Regex %s not found in %s" % (regex.pattern, machinefile))

            self.assertEqual(len(nub(mpi_instance.mpinodes)), len(machinefile.strip().split('\n')),
                             msg="mpinodes doesn't match the amount of nodes in the nodefile")

    def test_make_mympirundir(self):
        """test if the mympirundir is made"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.make_mympirundir()
        self.assertTrue(mpi_instance.mympirundir and os.path.isdir(mpi_instance.mympirundir),
                        msg="mympirundir has not been set or has not been created")

    def test_make_mpdboot(self):
        """test if the mpdboot conffile is made and has the correct permissions"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.make_mpdboot()
        mpdconffn = os.path.expanduser('~/.mpd.conf')
        self.assertTrue(os.path.isfile(mpdconffn), msg="mpd.conf has not been created")
        perms = stat.S_IMODE(os.stat(mpdconffn).st_mode)
        self.assertEqual(perms, stat.S_IREAD, msg='permissions %0o for mpd.conf %s' % (perms, mpdconffn))

    def test_set_mpdboot_localhost_interface(self):
        """test if mpdboot_localhost_interface is set correctly"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.set_mpdboot_localhost_interface()
        (nodename, iface) = mpi_instance.mpdboot_localhost_interface
        self.assertTrue(mpi_instance.mpdboot_localhost_interface and nodename and iface)
        self.assertTrue((nodename, iface) in mpi_instance.get_localhosts(),
                        msg=("mpdboot_localhost_interface is not a result from get_localhosts, nodename: %s,"
                             " iface: %s, get_localhosts: %s"))

    def test_get_localhosts(self):
        """test if localhost returns a list containing that are sourced correctly"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        res = mpi_instance.get_localhosts()
        _, out = run("/sbin/ip -4 -o addr show")

        print("localhosts: %s" % res)

        for (nodename, interface) in res:
            self.assertTrue(nodename in mpi_instance.nodes,
                            msg="%s is not a node from the nodes list" % nodename)
            self.assertTrue(interface in out,
                            msg="%s can not be found in the output of `/sbin/ip -4 -o addr show`, output: %s" %
                            (interface, out))

    def test_set_mpiexec_global_options(self):
        """test if set_mpiexec_global_options merges os.environ and mpiexec_global_options"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())
        mpi_instance.set_mpiexec_global_options()
        self.assertEqual(mpi_instance.mpiexec_global_options['MKL_NUM_THREADS'], "1",
                         msg="MKL_NUM_THREADS is not equal to 1")

        print("MODULE_ENVIRONMENT_VARIABLES: %s" % mpi_instance.MODULE_ENVIRONMENT_VARIABLES)

        if not mpi_instance.options.noenvmodules:
            for env_var in mpi_instance.MODULE_ENVIRONMENT_VARIABLES:
                self.assertEqual(env_var in os.environ, env_var in mpi_instance.mpiexec_global_options,
                                 msg=("%s is set in os.environ xor mpiexec_global_options, it should be set for both"
                                      " or set for neither") % env_var)

    def test_set_mpiexec_opts_from_env(self):
        """test if mpiexec_opts_from_env only contains environment variables that start with the given prefix"""
        mpi_instance = getinstance(mpim.MPI, Local, MympirunOption())

        if not os.environ.has_key('PYTHONPATH'):
            os.environ[key] = "/example:/test/123"
        mpi_instance.set_mpiexec_opts_from_env()
        prefixes = mpi_instance.OPTS_FROM_ENV_FLAVOR_PREFIX
        prefixes += mpi_instance.OPTS_FROM_ENV_BASE_PREFIX
        prefixes += mpi_instance.options.variablesprefix

        print("opts_from_env: %s" % mpi_instance.mpiexec_opts_from_env)
        for env_var in mpi_instance.mpiexec_opts_from_env:
            self.assertTrue(env_var.startswith(tuple(prefixes)) or env_var in mpi_instance.OPTS_FROM_ENV_BASE,
                            msg="%s does not start with a correct prefix, prefixes %s" % (env_var, prefixes))
            self.assertTrue(env_var in os.environ, msg="%s is not in os.environ, while it should be" % env_var)

        self.assertTrue('PYTHONPATH' in mpi_instance.mpiexec_opts_from_env)


    def test_make_mpirun(self):
        """test if make_mpirun correctly builds the complete mpirun command"""
        inst = getinstance(mpim.MPI, Local, MympirunOption())
        inst.main()

        argspool = ['mpirun']
        argspool += inst.options.mpirunoptions if inst.options.mpirunoptions else []
        print("mpirunoptions: %s" % inst.options.mpirunoptions)
        argspool += inst.mpdboot_options
        print("mpdboot_options: %s" % inst.mpdboot_options)
        argspool += inst.mpiexec_options
        print("mpiexec_options: %s" % inst.mpiexec_options)
        argspool += inst.cmdargs
        print("cmdargs: %s" % inst.cmdargs)
        for arg in inst.mpirun_cmd:
            self.assertTrue(arg in argspool, msg="arg: %s, pool: %s" % (arg, argspool))

    def test_mympirun_aliases_setup(self):
        """Make sure that list of mympirun aliases included in setup.py is synced"""
        from setup import MYMPIRUN_ALIASES

        # make sure all modules in vsc.mympirun.mpi are imported
        for loader, modname, _ in pkgutil.walk_packages([os.path.dirname(mpim.__file__)]):
            loader.find_module(modname).load_module(modname)

        # determine actual list of mympirun aliases
        mympirun_aliases = ['myscoop']
        for mpiclass in get_subclasses(mpim.MPI):
            mympirun_aliases.extend(mpiclass._mpiscriptname_for)

        self.assertEqual(MYMPIRUN_ALIASES, nub(sorted(mympirun_aliases)))

    def test_fake_dirname(self):
        """Make sure dirname for 'fake' subdir is the same in both setup.py and vsc.mympirun.mpi.mpi"""
        from setup import FAKE_SUBDIRECTORY_NAME
        self.assertEqual(mpim.FAKE_SUBDIRECTORY_NAME, FAKE_SUBDIRECTORY_NAME)

    def test_get_universe_ncpus(self):
        """ Test mpinode scheduling for --universe option """
        inst = getinstance(mpim.MPI, Local, MympirunOption())
        inst.nodes = [
            'node1',
            'node1',
            'node1',
            'node2',
            'node2',
            'node2',
            'node2',
        ]
        inst.nodes_tot_cnt = len(inst.nodes)
        inst.nodes_uniq = nub(inst.nodes)
        options = {
            2: {'node1': 1, 'node2': 1},
            3: {'node1': 2, 'node2': 1},
            6: {'node1': 3, 'node2': 3}
        }
        for opt in options:
            inst.options.universe = opt
            inst.set_ppn()
            inst.set_mpinodes()
            universe_ppn = inst.get_universe_ncpus()
            self.assertEqual(universe_ppn, options[opt])

    def test_get_hybrid_ncpus(self):
        """ Test mpinode scheduling for --hybrid option """
        inst = getinstance(mpim.MPI, Local, MympirunOption())
        inst.nodes = ['node1']*4 + ['node2']*4
        inst.nodes_tot_cnt = len(inst.nodes)
        inst.nodes_uniq = nub(inst.nodes)
        options = range(1,9)
        for opt in options:
            inst.options.hybrid = opt
            inst.set_ppn()
            inst.set_mpinodes()
            hybrid_ppn = inst.mpinodes
            self.assertEqual(hybrid_ppn.count('node1'), opt)
            self.assertEqual(hybrid_ppn.count('node2'), opt)

    def test_make_mympirundir_basepaths(self):
        """Test if basepaths are different on every run"""
        basepaths = set()
        for i in range(10):
            inst = getinstance(mpim.MPI, Local, MympirunOption())
            inst.make_mympirundir()
            basepaths.add(inst.mympirundir)

        self.assertEqual(len(basepaths), 10)

    def test_version_in_range(self):
        """Test version_in_range function"""
        self.assertTrue(mpim.version_in_range('1.4.0', '1.2.0', '2.0'))
        self.assertTrue(mpim.version_in_range('1.4.0', '1.2.0', None))
        self.assertTrue(mpim.version_in_range('1.4.0', None, '2.0'))
        self.assertTrue(mpim.version_in_range('1.4.0', None, None)) # always true

        self.assertFalse(mpim.version_in_range('1.4.0', '1.6.0', '2.0'))
        self.assertFalse(mpim.version_in_range('1.4.0', '1.6.0', None))
        self.assertFalse(mpim.version_in_range('2.4.0', None, '2.0'))

    def test_sockets_per_node(self):
        """Test if sockets_per_node returns an integer"""
        mpi_instance = getinstance(OpenMPI, Local, MympirunOption())
        sockets = mpi_instance.determine_sockets_per_node()
        self.assertTrue(isinstance(sockets, int))
        self.assertTrue(sockets > 0)

        mpi_instance.options.sockets_per_node = 4
        self.assertTrue(mpi_instance.determine_sockets_per_node() == 4)
