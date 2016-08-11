#
# Copyright 2011-2016 Ghent University
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
Base MPI class, all actual classes should inherit from this one

@author: Stijn De Weirdt
@author: Jeroen De Clerck
"""

import os
import pkgutil
import random
import re
import resource
import shutil
import socket
import stat
import string
import subprocess
import time

from IPy import IP

from vsc.utils.fancylogger import getLogger
from vsc.utils.missing import get_subclasses, nub
from vsc.utils.run import run_simple, run_async_to_stdout, run_to_file

# part of the directory that contains the installed fakes
INSTALLATION_SUBDIRECTORY_NAME = '(VSC-tools|(?:vsc-)?mympirun)'
# the fake subdir to contain the fake mpirun symlink
# also hardcoded in setup.py !
FAKE_SUBDIRECTORY_NAME = 'fake'

LOGGER = getLogger()


def what_mpi(name):
    """
    Return the path of the selected mpirun and its class.

    @param name: The name of the executable used to run mympirun

    @return: A triplet containing the following variables:
      - The path to the executable used to run mympirun (should be the path to an mpirun implementation)
      - The corresponding python class of the MPI variant
      - The python classes of the supported MPI flavors (from the various .py files in mympirun/mpi)
    """

    # import all modules in this dir: http://stackoverflow.com/a/16853487
    for loader, modulename, _ in pkgutil.walk_packages([os.path.dirname(__file__)]):
        loader.find_module(modulename).load_module(modulename)

    supp_mpi_impl = get_subclasses(MPI)  # supported MPI implementations

    # remove fake mpirun from $PATH
    stripfake()

    # get the path of the mpirun executable
    mpirun_path = which('mpirun')
    if mpirun_path is None:
        # no MPI implementation installed
        LOGGER.warn("no mpirun command found")
        return None, None, supp_mpi_impl

    scriptname = os.path.basename(os.path.abspath(name))

    # check if mympirun was called by a known mpirun alias (like
    # ompirun for OpenMPI or mhmpirun for mpich)
    for mpi in supp_mpi_impl:
        if mpi._is_mpiscriptname_for(scriptname):
            LOGGER.debug("%s was used to call mympirun", scriptname)
            return scriptname, mpi, supp_mpi_impl

    # mympirun was not called through a known alias, so find out which MPI
    # implementation the user has installed
    for mpi in supp_mpi_impl:
        if mpi._is_mpirun_for(mpirun_path):
            return scriptname, mpi, supp_mpi_impl

    # no specific flavor found, default to mpirun_path
    LOGGER.warn("The executable that called mympirun (%s) isn't supported"
                ", defaulting to %s", name, mpirun_path)
    return mpirun_path, None, supp_mpi_impl


def stripfake():
    """
    If the user loaded the vsc-mympirun module but called mpirun, some $PATH trickery catches the attempt.
    This function removes the fake path trickery from $PATH (assumes (VSC-tools|mympirun)/1.0.0/bin/fake).
    """

    LOGGER.debug("PATH before stripfake(): %s", os.environ['PATH'])

    # compile a regex that matches the faked mpirun
    reg_fakepath = re.compile(
        r"" + os.sep.join(['.*?',
                           INSTALLATION_SUBDIRECTORY_NAME + '.*?',
                           'bin',
                           '%(fake_subdir)s(%(sep)s[^%(sep)s]*)?$' %
                           {
                               'fake_subdir': FAKE_SUBDIRECTORY_NAME,
                               'sep': os.sep
                           }
                          ]))

    oldpath = os.environ.get('PATH', '').split(os.pathsep)

    # remove all $PATH elements that match the fakepath regex
    os.environ['PATH'] = os.pathsep.join([x for x in oldpath if not reg_fakepath.match(x)])

    LOGGER.debug("PATH after stripfake(): %s", os.environ['PATH'])
    return


def which(cmd):
    """
    Return (first) path in $PATH for specified command, or None if command is not found.

    taken from easybuild/tools/filetools.py, 6/7/2016
    """
    paths = os.environ.get('PATH', '').split(os.pathsep)
    for path in paths:
        cmd_path = os.path.join(path, cmd)
        # only accept path is command is there, and both readable and executable
        if os.access(cmd_path, os.R_OK | os.X_OK):
            LOGGER.info("Command %s found at %s", cmd, cmd_path)
            return cmd_path
    LOGGER.warning("Could not find command '%s' (with permissions to read/execute it) in $PATH (%s)", cmd, paths)
    return None


class MPI(object):

    """
    Base MPI class to generate the mpirun command line.

    To add a new MPI class just create a new class that extends the MPI class, see http://stackoverflow.com/q/456672
    """

    RUNTIMEOPTION = None

    _mpirun_for = []
    _mpiscriptname_for = []
    _mpirun_version = None

    MPIRUN_LOCALHOSTNAME = 'localhost'

    DEFAULT_RSH = None

    HYDRA = None
    HYDRA_LAUNCHER_NAME = "launcher"

    DEVICE_LOCATION_MAP = {'ib': '/dev/infiniband', 'det': '/dev/det', 'shm': '/dev/shm', 'socket': None}
    DEVICE_ORDER = ['ib', 'det', 'shm', 'socket']
    DEVICE_MPIDEVICE_MAP = {'ib': 'rdma', 'det': 'det', 'shm': 'shm', 'socket': 'socket'}

    NETMASK_TYPE_MAP = {'ib': 'ib', 'det': 'eth', 'shm': 'eth', 'socket': 'eth'}

    PINNING_OVERRIDE_METHOD = 'numactl'
    PINNING_OVERRIDE_TYPE_DEFAULT = None

    REMOTE_OPTION_TEMPLATE = "--rsh=%(rsh)s"
    MPDBOOT_OPTIONS = []
    MPDBOOT_SET_INTERFACE = True

    MPIEXEC_TEMPLATE_GLOBAL_OPTION = "-genv %(name)s '%(value)s'"
    OPTS_FROM_ENV_TEMPLATE = "-x '%(name)s'"
    MPIEXEC_OPTIONS = []

    MODULE_ENVIRONMENT_VARIABLES = ['MODULEPATH', 'LOADEDMODULES', 'MODULESHOME']

    OPTS_FROM_ENV_BASE = ['LD_LIBRARY_PATH', 'PATH', 'PYTHONPATH', 'CLASSPATH', 'LD_PRELOAD', 'PYTHONUNBUFFERED']
    OPTS_FROM_ENV_BASE_PREFIX = ['OMP', 'MKL', 'KMP', 'DAPL', 'PSM', 'IPATH', 'TMI', 'PSC', 'O64', 'VSMP']
    OPTS_FROM_ENV_FLAVOR_PREFIX = []  # to be set per flavor

    def __init__(self, options, cmdargs, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)
        self.options = options
        self.cmdargs = cmdargs

        self.device = None

        self.hydra_info = None
        self.has_hydra = self._has_hydra()

        self.netmasktype = None
        self.netmask = None

        self.mympirunbasedir = None
        self.mympirundir = None

        self.mpdboot_node_filename = None
        self.mpdboot_options = None
        self.mpdboot_totalnum = None
        self.mpdboot_localhost_interface = None

        self.mpiexec_node_filename = None
        self.mpiexec_options = None
        self.mpiexec_global_options = {}
        self.mpiexec_opts_from_env = []  # list of variables

        self.mpirun_cmd = None

        self.pinning_override_type = getattr(self.options, 'overridepin', self.PINNING_OVERRIDE_TYPE_DEFAULT)

        super(MPI, self).__init__(**kwargs)

        # sanity checks
        if getattr(self, 'sched_id', None) is None:
            self.log.raiseException("__init__: sched_id is None (should be set by one of the Sched classes)")

        if not self.cmdargs:
            self.log.raiseException("__init__: no executable or command provided")

    # factory methods for MPI
    @classmethod
    def _is_mpirun_for(cls, mpirun_path):
        """
        Check if this class provides support for the mpirun that was called.

        @param cls: the class that calls this function
        @param mpirun_path: the path to the mpirun aka `which mpirun`

        @return: true if $mpirun_path is defined as an mpirun implementation of $cls
        """

        # regex matches "cls._mpirun_for/version number"
        reg = re.compile(r"(?:%s)%s(\d+(?:(?:\.|-)\d+(?:(?:\.|-)\d+\S+)?)?)" %
                         ("|".join(cls._mpirun_for), os.sep))
        reg_match = reg.search(mpirun_path)
        LOGGER.debug("_is_mpisrun_for(), reg_match: %s", reg_match)

        if reg_match:
            if cls._mpirun_version is None:
                return True
            else:
                # do version check (reg_match.group(1) is the version number)
                return cls._mpirun_version(reg_match.group(1))
        else:
            return False

    @classmethod
    def _is_mpiscriptname_for(cls, scriptname):
        """
        Check if this class provides support for scriptname.

        @param cls: the class that calls this function
        @param scriptname: the executable that called mympirun

        @return: true if $scriptname is defined as an mpiscriptname of $cls
        """

        return scriptname in cls._mpiscriptname_for

    # other general functionality
    def _has_hydra(self):
        """Has HYDRA or not"""
        return self.HYDRA

    ### main ###
    def main(self):
        """Main method"""
        self.prepare()

        self.make_mpdboot()

        # prepare these separately
        self.set_mpiexec_global_options()
        self.set_mpiexec_opts_from_env()

        self.set_mpiexec_options()

        self.make_mpirun()

        # actual execution
        for runfunc, cmd in self.mpirun_prepare_execution():
            self.log.debug("main: going to execute cmd %s", " ".join(cmd))
            if self.options.output:
                self.log.info("writing mpirun output to %s", self.log.output)
            exitcode, _ = runfunc(cmd)
            if exitcode > 0:
                self.cleanup()
                self.log.raiseException("main: exitcode %s > 0; cmd %s" % (exitcode, cmd))
                break

        self.cleanup()

    ### BEGIN prepare ###
    def prepare(self):
        """Collect information to create the commands."""
        self.check_usable_cpus()
        self.check_limit()

        self.set_omp_threads()

        self.set_netmask()

        self.make_node_file()

        self.set_pinning()

    def check_usable_cpus(self):
        """Check and log if non-standard cpus (eg due to cpusets)."""
        if not self.foundppn == len(self.cpus):
            self.log.info("check_usable_cpus: non-standard cpus found: requested ppn %s, found cpus %s, usable cpus %s",
                          self.ppn, self.foundppn, len(self.cpus))

    def check_limit(self):
        """Check if the softlimit of the stack exceeds 1MB, if it doesn't, show an error."""
        soft, _ = resource.getrlimit(resource.RLIMIT_STACK)  # in bytes
        if soft > -1 and soft < 1024 * 1024:
            # non-fatal
            self.log.error("Stack size %s%s too low? Increase with ulimit -s unlimited", soft, 'kB')

    def set_omp_threads(self):
        """
        Sets ompthreads to the amount of threads every MPI process should use.

        For example, with hybrid 2 every MPI process should have a total 2 threads (each on a seperate processors).
        This way each node will have 8 MPI processes (assuming ppn is 16). Will default to 1 if hybrid is disabled.
        """
        if 'OMP_NUM_THREADS' in os.environ:
            threads = os.environ['OMP_NUM_THREADS']
        else:
            if not self.options.hybrid:
                threads = 1
            else:
                threads = max(self.ppn // self.options.hybrid, 1)

        self.log.debug("Set OMP_NUM_THREADS to %s", threads)

        os.environ['OMP_NUM_THREADS'] = str(threads)

        setattr(self.options, 'ompthreads', threads)

    def set_netmask(self):
        """
        Set self.netmask to a list containing (ip address/netmask).

        Based on the hosts IP address (from ip addr show) and the selected netmasktype from select_device.
        """
        if self.netmasktype is None:
            self.select_device()

        device_ip_reg_map = {
            'eth': r"ether.*?\n.*?inet\s+(\d+\.\d+.\d+.\d+/\d+)",
            'ib': r"infiniband.*?\n.*?inet\s+(\d+\.\d+.\d+.\d+/\d+)",
            }

        if self.netmasktype not in device_ip_reg_map:
            self.log.raiseException("set_netmask: can't get netmask for %s: unknown mode (device_ip_reg_map %s)" %
                                    (self.netmasktype, device_ip_reg_map))

        cmd = "/sbin/ip addr show"
        exitcode, out = run_simple(cmd)
        if exitcode > 0:
            self.log.raiseException("set_netmask: failed to run cmd %s, ec: %s" % (cmd, exitcode))

        reg = re.compile(device_ip_reg_map[self.netmasktype])
        if not reg.search(out):
            self.log.raiseException("set_netmask: can't get netmask for %s: no matches found (reg %s out %s)" %
                                    (self.netmasktype, device_ip_reg_map[self.netmasktype], out))

        res = []
        for ipaddr_mask in reg.finditer(out):
            ip_info = IP(ipaddr_mask.group(1), make_net=True)
            network_netmask = "%s/%s" % (ip_info.net(), ip_info.netmask())
            res.append(network_netmask)
            self.log.debug("set_netmask: convert ipaddr_mask %s into network_netmask %s",
                           ipaddr_mask.group(1), network_netmask)

        self.log.debug("set_netmask: return complete netmask %s", res)
        if res:
            self.netmask = os.pathsep.join(res)

    def select_device(self, force=False):
        """
        Select a device (such as infiniband), either with command line arguments or the best available.
        See DEVICE_ORDER for order of preference.
        """
        if self.device is not None and not force:
            self.log.debug("select_device: device already set: %s", self.device)
            return

        founddev = None
        if getattr(self.options, 'rdma', None):
            founddev = 'ib'
            self.set_device(founddev)

        elif getattr(self.options, 'socket', None):
            founddev = 'socket'
            self.set_device(founddev)

        else:
            for dev in self.DEVICE_ORDER:
                if dev in ('shm',):
                    # only use shm if a single node is used
                    if self.nruniquenodes > 1:
                        continue

                path = self.DEVICE_LOCATION_MAP[dev]
                if path is None or os.path.exists(path):
                    founddev = dev
                    self.device = self.DEVICE_MPIDEVICE_MAP[dev]
                    self.log.debug("select_device: found path %s for device %s", path, self.device)
                    break

        if self.device is None:
            self.log.raiseException("select_device: failed to set device.")

        self.netmasktype = self.NETMASK_TYPE_MAP[founddev]
        self.log.debug("select_device: set netmasktype %s for device %s (founddev %s)",
                       self.netmasktype, self.device, founddev)

    def set_device(self, founddev):
        """Set self.device to founddev, but doublecheck if the path to this device actually exists """
        self.device = self.DEVICE_MPIDEVICE_MAP[founddev]
        path = self.DEVICE_LOCATION_MAP[founddev]
        if path is None or not os.path.exists(path):
            self.log.warning("Forcing device %s (founddevice %s), but path %s not found.",
                             self.device, founddev, path)

    def make_node_file(self):
        """
        Make a nodefile and mpdbootfile.

        Parses the list of nodes that run an MPI process and writes this information to a nodefile.
        Also parses the list of unique nodes and writes this information to a mpdbootfile
        (based on hyrda and universe options).
        """
        self.make_mympirundir()

        if self.mpinodes is None:
            self.make_node_list()

        nodetxt = "\n".join(self.mpinodes + [''])

        mpdboottxt = ""
        for uniquenode in self.uniquenodes:
            txt = uniquenode
            if not self.has_hydra:
                if self.options.universe is not None and self.options.universe > 0:
                    txt += ":%s" % self.get_universe_ncpus()
                txt += " ifhn=%s" % uniquenode

            mpdboottxt += "%s\n" % txt

        try:
            nodefn = os.path.join(self.mympirundir, 'nodes')
            open(nodefn, 'w').write(nodetxt)
            self.mpiexec_node_filename = nodefn
            self.log.debug("make_node_file: wrote nodefile %s:\n%s", nodefn, nodetxt)

            mpdfn = os.path.join(self.mympirundir, 'mpdboot')
            open(mpdfn, 'w').write(mpdboottxt)
            self.mpdboot_node_filename = mpdfn
            self.log.debug("make_node_file: wrote mpdbootfile %s:\n%s", mpdfn, mpdboottxt)
        except Exception:
            self.log.raiseException('make_node_file: failed to write nodefile %s mpbboot nodefile %s' % (nodefn, mpdfn))

    def get_universe_ncpus(self):
        """Return ppn for universe"""
        return self.mpiprocesspernode

    def make_mympirundir(self):
        """
        Make a dir called .mympirun_id_timestamp in either the given basepath or $HOME.

        Temporary files such as the nodefile will be written to this directory.
        Allows for easy cleanup after finishing the script.
        """
        basepath = getattr(self.options, 'basepath', None)
        if basepath is None:
            basepath = os.environ['HOME']
        if not os.path.exists(basepath):
            self.log.raiseException("make_mympirun_dir: basepath %s should exist." % basepath)

        self.mympirunbasedir = os.path.join(basepath, '.mympirun')
        destdir = os.path.join(self.mympirunbasedir, "%s_%s" % (self.sched_id, time.strftime("%Y%m%d_%H%M%S")))
        if not os.path.exists(destdir):
            try:
                os.makedirs(destdir)
            except os.error:
                self.log.raiseException('make_mympirun_dir: failed to make job dir %s' % destdir)

        self.log.debug("make_mympirun_dir: tmp mympirundir %s", destdir)
        self.mympirundir = destdir

    ### BEGIN pinning ###
    def set_pinning(self, mp=None):
        if not hasattr(self.options, 'pinmpi'):
            setattr(self.options, 'pinmpi', None)

        mp = self._pin_flavour(mp)

        if isinstance(mp, bool):
            self.log.debug("set_pinning: setting pin_flavour %s", mp)
            self.options.pinmpi = mp

        if not isinstance(self.options.pinmpi, bool):
            if self.options.hybrid is not None:
                # always pin!
                self.options.pinmpi = True
            else:
                # always pin!
                self.options.pinmpi = True

        if self.pinning_override_type is not None:
            self.log.debug("set_pinning: previous pinning %s;  will be overwritten, pinning_override_type set to %s",
                           self.options.pinmpi, self.pinning_override_type)
            self.options.pinmpi = False
        else:
            self.log.debug("set_pinning: pinmpi %s", self.options.pinmpi)

    def _pin_flavour(self, mp=None):
        return mp

    ### BEGIN mpdboot ###
    def make_mpdboot(self):
        """
        Make the mpdboot configuration.

        Read a password from ~/.mpd.conf (if this does not exist, create it).
        """
        # check .mpd.conf existence
        mpdconffn = os.path.expanduser('~/.mpd.conf')
        if not os.path.exists(mpdconffn):
            self.log.warning(("make_mpdboot: mpd.conf file not found at %s. Creating this file "
                              "(text file with minimal entry 'password=<somesecretpassword>')"), mpdconffn)
            mpdconff = open(mpdconffn, 'w')
            mpdconff.write("password=%s" % ''.join(random.choice(string.ascii_uppercase + string.digits)
                                                   for x in range(10)))
            mpdconff.close()
            # set correct permissions on this file.
            os.chmod(mpdconffn, stat.S_IREAD)

        self.set_mpdboot_localhost_interface()

        self.make_mpdboot_options()

        self.log.debug("make_mpdboot set options %s", self.mpdboot_options)

    def set_mpdboot_localhost_interface(self):
        """Sets mpdboot_localhost_interface to the first result of get_localhosts()."""
        localhosts = self.get_localhosts()
        if len(localhosts) > 1:
            self.log.warning(("set_mpdboot_localhost_interface: more then one match for localhost from unique nodes "
                              " found %s, using 1st."), localhosts)
        nodename, iface = localhosts[0]  # take the first one
        self.log.debug("set_mpdboot_localhost_interface: mpd localhost interface %s found for %s", iface, nodename)
        self.mpdboot_localhost_interface = (nodename, iface)

    def get_localhosts(self):
        """
        Get the localhost interfaces, based on the hostnames from the nodes in self.uniquenodes.

        Raises Exception if no localhost interface was found.

        @return: the list of interfaces that correspond to the list of uniquenodes
        """
        iface_prefix = ['eth', 'em', 'ib', 'wlan']
        reg_iface = re.compile(r'((?:%s)\d+(?:\.\d+)?(?::\d+)?|lo)' % '|'.join(iface_prefix))

        # iterate over uniquenodes and get their interfaces
        # add the found interface to res if it matches reg_iface
        res = []
        for idx, nodename in enumerate(self.uniquenodes):
            ip = socket.gethostbyname(nodename)
            cmd = "/sbin/ip -4 -o addr show to %s/32" % ip
            exitcode, out = run_simple(cmd)
            if exitcode == 0:
                regex = reg_iface.search(out)
                if regex:
                    iface = regex.group(1)
                    self.log.debug("get_localhost idx %s: localhost interface %s found for %s (ip: %s)",
                                   idx, iface, nodename, ip)

                    res.append((nodename, iface))
                else:
                    self.log.debug("get_localhost idx %s: no interface match for prefixes %s out %s",
                                   idx, iface_prefix, out)
            else:
                self.log.error("get_localhost idx %s: cmd %s failed with output %s", idx, cmd, out)

        if not res:
            self.log.raiseException("get_localhost: can't find localhost from uniq nodes %s" % self.uniquenodes)
        return res

    def make_mpdboot_options(self):
        """Add various options to mpdboot_options"""

        self.mpdboot_options = self.MPDBOOT_OPTIONS[:]

        # add the mpd nodefile to mpdboot options
        self.mpdboot_options.append("--file=%s" % self.mpdboot_node_filename)

        # add the interface to mpdboot options
        if self.MPDBOOT_SET_INTERFACE:
            if self.has_hydra:
                iface = "-iface %s" % self.mpdboot_localhost_interface[1]
            else:
                iface = "--ifhn=%s" % self.mpdboot_localhost_interface[0]
            self.log.debug('Set mpdboot interface option "%s"', iface)
            self.mpdboot_options.append(iface)
        else:
            self.log.debug('No mpdboot interface option')

        # add the number of mpi processes (aka mpi universe) to mpdboot options
        if self.options.universe is not None and self.options.universe > 0:
            self.mpdboot_options.append("--ncpus=%s" % self.get_universe_ncpus())

        # add nr of unique nodes as totalnum if defined
        if self.mpdboot_totalnum:
            self.mpdboot_options.append("--totalnum=%s" % self.mpdboot_totalnum)

        # set verbosity
        if self.options.mpdbootverbose:
            self.mpdboot_options.append("--verbose")

        # mpdboot rsh command
        if not self.has_hydra:
            self.mpdboot_options.append(self.REMOTE_OPTION_TEMPLATE % {'rsh': self.get_rsh()})

    ### BEGIN mpiexec ###
    def set_mpiexec_global_options(self):
        """
        Set mpiexec_global_options.

        Unless explicitly asked not to, will add all environment variables to mpiexec_global_options.
        """
        self.mpiexec_global_options['MKL_NUM_THREADS'] = '1'

        if not self.options.noenvmodules:
            for env_var in self.MODULE_ENVIRONMENT_VARIABLES:
                if env_var in os.environ and env_var not in self.mpiexec_global_options:
                    self.mpiexec_global_options[env_var] = os.environ[env_var]

    def set_mpiexec_opts_from_env(self):
        """
        Get relevant environment variables and append them to mpiexec_opts_from_env

        Gets the union of OPTS_FROM_ENV_BASE and the environment variables that start with a given prefix.
        These will then be parsed and passed to mpiexec as an option
        """

        # get all unique variables that are both in os.environ and in OPTS_FROM_ENV_BASE
        vars_to_pass = nub(filter(os.environ.has_key, self.OPTS_FROM_ENV_BASE))

        for env_prefix in self.OPTS_FROM_ENV_FLAVOR_PREFIX + self.OPTS_FROM_ENV_BASE_PREFIX + self.options.variablesprefix:
            for env_var in os.environ.keys():
                # add all environment variable keys that are equal to <prefix> or start with <prefix>_
                # to mpiexec_opts_from_env, but only if they aren't already in vars_to_pass
                if (env_prefix == env_var or env_var.startswith("%s_" % env_prefix)) and env_var not in vars_to_pass:
                    self.mpiexec_opts_from_env.append(env_var)

    def set_mpiexec_options(self):
        """Add various options to mpiexec_options."""
        self.mpiexec_options = self.MPIEXEC_OPTIONS[:]

        if self.has_hydra:
            self.make_mpiexec_hydra_options()
        else:
            self.mpiexec_options.append("-machinefile %s" % self.mpiexec_node_filename)

        # mpdboot global variables
        self.mpiexec_options += self.get_mpiexec_global_options()

        # number of procs to start
        if self.options.universe is not None and self.options.universe > 0:
            self.mpiexec_options.append("-np %s" % self.options.universe)
        else:
            self.mpiexec_options.append("-np %s" % (self.mpiprocesspernode * self.nruniquenodes))

        # pass local env variables to mpiexec
        self.mpiexec_options += self.get_mpiexec_opts_from_env()

    def make_mpiexec_hydra_options(self):
        """Hydra specific mpiexec options."""
        self.get_hydra_info()
        self.mpiexec_options.append("--hostfile %s" % self.mpiexec_node_filename)
        if self.options.branchcount is not None:
            self.mpiexec_options.append("--branch-count %d" % self.options.branchcount)

        # default launcher seems ssh
        if getattr(self, 'HYDRA_RMK', None) is not None:
            rmk = [x for x in self.HYDRA_RMK if x in self.hydra_info.get('rmk', [])]
            if len(rmk) > 0:
                self.log.debug("make_mpiexe_hydra_options: HYDRA: rmk %s, using first", rmk)
                self.mpiexec_options.append("-rmk %s" % rmk[0])
            else:
                self.log.debug("make_mpiexe_hydra_options: no rmk from HYDRA_RMK %s and hydra_info %s",
                               self.HYDRA_RMK, self.hydra_info)
        else:
            launcher = None
            if getattr(self, 'HYDRA_LAUNCHER', None) is not None:
                launcher = [x for x in self.HYDRA_LAUNCHER if x in self.hydra_info.get('launcher', [])]
                if launcher:
                    self.log.debug("make_mpiexec_hydra_options: HYDRA: launcher %s, using first one", launcher)
                else:
                    self.log.debug("make_mpiexe_hydra_options: no launcher from HYDRA_LAUNCHER %s and hydra_info %s",
                                   self.HYDRA_LAUNCHER, self.hydra_info)

            launcher_exec = self.HYDRA_LAUNCHER_EXEC
            if not launcher:
                launcher_exec = self.get_rsh()
            else:
                self.mpiexec_options.append("-%s %s" % (self.HYDRA_LAUNCHER_NAME, launcher[0]))

            if launcher_exec is not None:
                self.log.debug("make_mpiexec_hydra_options: HYDRA using launcher exec %s", launcher_exec)
                self.mpiexec_options.append("-%s-exec %s" % (self.HYDRA_LAUNCHER_NAME, launcher_exec))

    def get_hydra_info(self):
        """Get a dict with hydra info."""
        reg_hydra_info = re.compile(r"^\s+(?P<key>\S[^:\n]*)\s*:(?P<value>.*?)\s*$", re.M)

        cmd = "mpirun -info"
        exitcode, out = run_simple(cmd)
        if exitcode > 0:
            self.log.raiseException("get_hydra_info: failed to run cmd %s: %s" % (cmd, out))

        hydra_info = {}
        for regex in reg_hydra_info.finditer(out):
            key = regex.groupdict()['key']
            if key is None:
                self.log.raiseException("get_hydra_info: failed to get hydra info: missing key in %s (out: %s)" %
                                        (regex.groupdict(), out))
            key = key.strip().lower()
            value = regex.groupdict()['value']
            if value is None:
                self.log.debug("get_hydra_info: failed to get hydra info: missing value in %s (out: %s)" %
                               (regex.groupdict(), out))
                value = ''
            values = [x.strip().strip('"').strip("'") for x in value.split() if x.strip()]
            hydra_info[key] = values
        self.log.debug("get_hydra_info: found info %s", hydra_info)

        keymap = {
            "rmk": r'^resource\s+management\s+kernel.*available',
            "launcher": r'^%s.*available' % self.HYDRA_LAUNCHER_NAME,
            "chkpt": r'^checkpointing.*available',
            }

        self.hydra_info = {}
        for newkey, regtxt in keymap.items():
            reg = re.compile(regtxt, re.I)
            matches = [v for k, v in hydra_info.items() if reg.search(k)]
            if len(matches) == 0:
                continue
            else:
                if len(matches) > 1:
                    self.log.warning("get_hydra_info: more than one match %s found: newkey %s regtxt %s hydrainfo %s",
                                     matches, newkey, regtxt, hydra_info)
                self.hydra_info[newkey] = matches[0]

        self.log.debug("get_hydra_info: filtered info %s", self.hydra_info)

    def get_mpiexec_global_options(self):
        """
        Create the global options to pass to mpiexec.

        Iterates over mpiexec_global_options, and picks the options that aren't already in mpiexec_opts_from_env.
        This way the options that are set with environment variables get a higher priority.

        @return: the final list of options, including the correct command line argument for the mpi flavor
        """
        global_options = []

        for key, val in self.mpiexec_global_options.items():
            if key in self.mpiexec_opts_from_env:
                # environment variable is already set
                self.log.debug("get_mpiexec_global_options: found global option %s in mpiexec_opts_from_env.", key)
            else:
                # insert the keyvalue pair into the correct command line argument
                # the command for setting the environment variable depends on the mpi flavor
                global_options.append(self.MPIEXEC_TEMPLATE_GLOBAL_OPTION % {'name': key, "value": val})

        self.log.debug("get_mpiexec_global_options: template %s return options %s",
                       self.MPIEXEC_TEMPLATE_GLOBAL_OPTION, global_options)
        return global_options

    def get_mpiexec_opts_from_env(self):
        """
        gets the environment variables that should be passed to mpiexec as an option.

        Parses mpiexec_opts_from_env so that the chosen mpi flavor can understand it when it is passed to the
        command line argument.
        """

        self.log.debug("get_mpiexec_opts_from_env: variables (and current value) to pass: %s",
                       [[x, os.environ[x]] for x in self.mpiexec_opts_from_env])

        if '%(commaseparated)s' in self.OPTS_FROM_ENV_TEMPLATE:
            self.log.debug("get_mpiexec_opts_from_env: found commaseparated in template.")
            environment_options = [self.OPTS_FROM_ENV_TEMPLATE %
                                   {'commaseparated': ','.join(self.mpiexec_opts_from_env)}]
        else:
            environment_options = [self.OPTS_FROM_ENV_TEMPLATE %
                                   {'name': x, 'value': os.environ[x]} for x in self.mpiexec_opts_from_env]

        self.log.debug("get_mpiexec_opts_from_env: template %s return options %s",
                       self.OPTS_FROM_ENV_TEMPLATE, environment_options)
        return environment_options

    ### BEGIN mpirun ###
    def make_mpirun(self):
        """Make the mpirun command (or whatever). It typically consists of a mpdboot and a mpiexec part."""

        self.mpirun_cmd = ['mpirun']

        self._make_final_mpirun_cmd()
        if self.options.mpirunoptions is not None:
            self.mpirun_cmd.append(self.options.mpirunoptions)
            self.log.debug("make_mpirun: added user provided options %s", self.options.mpirunoptions)

        if self.pinning_override_type is not None:
            p_o = self.pinning_override()
            if p_o is None or not os.path.isfile(p_o):
                self.log.raiseException("make_mpirun: no valid pinning_overrride %s (see previous errors)" % p_o)
            else:
                self.mpirun_cmd += [p_o]

        # the executable
        # use undocumented subprocess API call to quote whitespace (executed with Popen(shell=True))
        # (see http://stackoverflow.com/questions/4748344/whats-the-reverse-of-shlex-split for alternatives if needed)
        quoted_args_string = subprocess.list2cmdline(self.cmdargs)
        self.log.debug("make_mpirun: adding cmdargs %s (quoted %s)", self.cmdargs, quoted_args_string)
        self.mpirun_cmd.append(quoted_args_string)

    def _make_final_mpirun_cmd(self):
        """
        Create the acual mpirun command.

        Append the mpdboot and mpiexec options to the command.
        """
        self.mpirun_cmd += self.mpdboot_options
        self.mpirun_cmd += self.mpiexec_options

    def pinning_override(self):
        """
        Create own pinning
          - using taskset or numactl?
          - start the real executable with correct pinning

        There are self.mpiprocesspernode number of processes to start on (self.nruniquenodes * self.ppn) requested slots
        Each node has to accept self.mpiprocesspernode/self.ppn processes over self.ppn number of cpu slots

        Do we assume heterogenous nodes (ie same cpu layout as current node?)
          - We should but in reality we don't because of different cpusets!

        What do we support?
          - packed/compact : all together, ranks close to each other
          - spread: as far away as possible from each other

        Option:
          - threaded (default yes): eg in hybrid, pin on all available cores or just one

        When in this mode, one needs to disable default/native pinning

        There seems no clean way to simply prefix the variables before the real exe
          - some mpirun are binary, others are bash
            - no clean way to pass the variable
              - a simple bash script also resolves the csh problem?

        Simple shell check. This is the login shell of the current user
          - not necessarily the current shell
            - but it is when multinode is used i think (eg startup with ssh)
        """
        variableexpression = self.get_pinning_override_variable()
        if variableexpression is None:
            self.log.raiseException("pinning_override: no variable name found/set.")

        self.log.debug("pinning_override: using variable expression %s as local node rank.", variableexpression)

        rankname = 'MYMPIRUN_LOCALRANK'
        rankmapname = 'MYMPIRUN_LOCALRANK_MAP'

        wrappertxt = "#!/bin/bash\n%s=%s\n" % (rankname, variableexpression)

        # number of local processors
        # - eg numactl -s grep physcpubind
        if not self.ppn == self.foundppn:
            self.log.raiseException(("pinning_override: number of found procs %s is different from "
                                     "requested ppn %s. Not yet supported.") % (self.foundppn, self.ppn))

        override_type = self.pinning_override_type
        multithread = True
        if override_type.endswith('pin'):
            override_type = override_type[:-3]
            multithread = False
        self.log.debug("pinning_override: type %s multithread %s", override_type, multithread)

        # The whole method is very primitive
        # - assume cpu layout on OS has correct numbering
        # What about pinned threads of threaded apps?
        # - eg use likwid to pin those threads too

        # cores per process
        corespp = self.foundppn // self.mpiprocesspernode
        corespp_rest = self.foundppn % self.mpiprocesspernode
        if (corespp < 1) or (self.mpiprocesspernode == self.foundppn):
            multi = False
            self.log.debug(("pinning_override: exactly one or more than one process for each core: mpi processes: %s "
                            "ppn: %s. Multithreading is disabled."), self.mpiprocesspernode, self.foundppn)
        if corespp_rest > 0:
            self.log.debug(("pinning_override: number of mpiprocesses (%s) is not an exact multiple of "
                            "number of procs (%s). Ignoring rest."), self.mpiprocesspernode, self.foundppn)

        map_func = None
        if override_type in ('packed', 'compact',):
            if multi:
                # consecutive domains
                map_func = lambda x: "%s-%s" % (x * corespp, (x + 1) * corespp - 1)
            else:
                # consecutive cores
                map_func = lambda x: x
        elif override_type in ('cycle',):
            # eg double with GAMESS
            if multi:
                self.log.raiseException(
                    "pinning_override: trying to set pin type to 'cycle' with multithreading enabled: not supported")
            else:
                map_func = lambda x: (x % self.foundppn)
        elif override_type in ('spread',):
            if multi:
                # spread domains
                map_func = lambda x: "%s-%s" % (x * corespp, (x + 1) * corespp - 1)
            else:
                # spread cores
                map_func = lambda x: (x * corespp)
        else:
            self.log.raiseException("pinning_override: unsupported pinning_override_type  %s" %
                                    self.pinning_override_type)

        rankmap = [map_func(x) for x in range(self.mpiprocesspernode)]

        wrappertxt += "%s=(%s)\n" % (rankmapname, ' '.join(rankmap))

        pinning_exe = which(self.PINNING_OVERRIDE_METHOD)  # default numactl
        if not pinning_exe:
            self.log.raiseException("pinning_override: can't find executable %s" % self.PINNING_OVERRIDE_METHOD)

        if self.PINNING_OVERRIDE_METHOD in ('numactl',):
            pinning_exe += ' --physcpubind="${%s[$%s]}"' % (rankmapname, rankname)

        wrappertxt += "%s $@" % pinning_exe
        wrapperpath = os.path.join(self.jobdir, 'pinning_override_wrapper.sh')
        try:
            open(wrapperpath, 'w').write(wrappertxt)
            os.chmod(wrapperpath, stat.S_IRWXU)
            self.log.debug("pinning_override: wrote wrapper file %s:\n%s", wrapperpath, wrappertxt)
        except IOError:
            self.log.raiseException('pinning_override: failed to write wrapper file %s', wrapperpath)

        self.log.debug("pinning_override: pinning_exe %s to wrapper %s", pinning_exe, wrapperpath)

        return wrapperpath

    def get_pinning_override_variable(self):
        """
        Key element is that one needs to know the rank or something similar of each process
          - preferably in environment
            - eg QLogic PSC_MPI_NODE_RANK: this instance is the nth local rank.
          - alternative is small c mpi program with bash wrapper
            - see also likwid-mpirun for alternative example
              - mentions similar OMPI_COMM_WORLD_RANK for OpenMPI and PMI_RANK for IntelMPI
                - local_rank is remainder of myrank diveded by number of nodes?

        This is a bash expression.
          - eg $((x/y)) is also fine
        """
        self.log.raiseException("get_pinning_override_variable: not implemented.")

    def mpirun_prepare_execution(self):
        """
        Make a function that runs mpirun with all arguments correctly set

        @return: a tuple containing the final function and the final command
        """

        def main_runfunc(cmd):
            """The function that will run mpirun"""
            if self.options.output is not None:
                return run_to_file(cmd, filename=self.options.output)
            else:
                return run_async_to_stdout(cmd)

        return [(main_runfunc, self.mpirun_cmd)]

    def cleanup(self):
        """Remove temporary directory (mympirundir)"""
        try:
            shutil.rmtree(self.mympirundir)
            self.log.debug("cleanup: removed mympirundir %s", self.mympirundir)
        except OSError:
            self.log.raiseException("cleanup: cleaning up mympirundir %s failed" % self.mympirundir)
