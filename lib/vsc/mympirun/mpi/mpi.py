#
# Copyright 2011-2020 Ghent University
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
@author: Caroline De Brouwer
"""
from __future__ import print_function

import os
import random
import re
import resource
import shutil
import socket
import stat
import string
import sys
import time

from IPy import IP
from vsc.utils.fancylogger import getLogger
from vsc.mympirun.common import MpiBase
from vsc.utils.missing import nub
from vsc.utils.run import CmdList, RunNoShell, RunAsyncLoopStdout, RunFile, RunLoop, run

RM_HYDRA_LAUNCHER = 'RM_HYDRA_LAUNCHER'

# size of dir in bytes
TEMPDIR_WARN_SIZE = 100000
TEMPDIR_ERROR_SIZE = 1000000

TIMEOUT_CODE = 124
TIMEOUT_WARNING = """mympirun has been running for %s seconds without seeing any output.
This may mean that your program is hanging, please check and make sure that is not the case!

If this warning is printed too soon and the program is doing useful work without producing any output,
you can increase the timeout threshold via --output-check-timeout (current setting: %s seconds)"""

TIMEOUT_FATAL_MSG = "This is considered fatal (unless --disable-output-check-fatal is used)"


class RunMPI(RunNoShell):
    """
    Parent class for Run classes for MPI
    """

    def loop_process_output_common(self):
        """
        Common code for _loop_process_output in RunFileLoopMPI and RunAsyncMPI
        """
        time_passed = self.LOOP_TIMEOUT_INIT + self._loop_count * self.LOOP_TIMEOUT_MAIN
        if not self.seen_output and time_passed > self.output_timeout:
            msg = TIMEOUT_WARNING % (time_passed, self.output_timeout)
            # avoid getting warning multiple times by setting seen_output to True if a warning was produced
            self.seen_output = True
            self.log.warn(msg)
            if self.fatal_no_output:
                self.stop_tasks()
                self.log.error(TIMEOUT_FATAL_MSG)
                sys.exit(TIMEOUT_CODE)


class RunFileLoopMPI(RunFile, RunLoop, RunMPI):
    """
    Combination of RunFile and RunLoop to support output to file,
    while also checking whether any output has been produced after a specified amount of time.
    """
    def __init__(self, cmd, **kwargs):
        """
        handle initialisation: get filename and output timeout from arguments
        """
        self.output_timeout = kwargs.pop('output_timeout', None)
        self.fatal_no_output = kwargs.pop('fatal_no_output', None)

        super(RunFileLoopMPI, self).__init__(cmd, **kwargs)

        self.seen_output = self.output_timeout < 0 #no check when output_timeout is negative

    def _loop_process_output(self, output):
        """
        check if process is generating any output at all; if not, warn the user after a set amount of time
        """
        if output:
            raise ValueError("Output was found using RunFile:\n%s\n This means something went horribly wrong." % output)

        if self.seen_output:
            return
        try:
            self.seen_output = self.filehandle.tell() > 0
        except IOError as err:
            raise IOError("Couldn't check file size; %s" % err)

        self.loop_process_output_common()


class RunAsyncMPI(RunAsyncLoopStdout, RunMPI):
    """
    Stream output to stdout as in RunAsyncLoopStdout
    while also checking whether any output has been produced after a specified amount of time.

    """
    def __init__(self, cmd, **kwargs):
        self.output_timeout = kwargs.pop('output_timeout', None)
        self.fatal_no_output = kwargs.pop('fatal_no_output', None)

        super(RunAsyncMPI, self).__init__(cmd, **kwargs)
        # no check when output_timeout is negative
        self.seen_output = self.output_timeout < 0

    def _loop_process_output(self, output):
        """ Send output to stdout + hang check """
        if len(output) > 0:
            self.seen_output = True

        self.loop_process_output_common()

        super(RunAsyncMPI, self)._loop_process_output(output)


class MPI(MpiBase):
    """
    Base MPI class to generate the mpirun command line.

    To add a new MPI class just create a new class that extends the MPI class, see http://stackoverflow.com/q/456672
    """

    MPIRUN_LOCALHOSTNAME = 'localhost'

    HYDRA = None
    HYDRA_LAUNCHER_NAME = "launcher"

    DEVICE_LOCATION_MAP = {
        'ib': '/dev/infiniband',
        'det': '/dev/det',
        'shm': '/dev/shm',
        'socket': None,
    }
    DEVICE_ORDER = ['ib', 'det', 'shm', 'socket']
    DEVICE_MPIDEVICE_MAP = {
        'ib': 'rdma',
        'det': 'det',
        'shm': 'shm',
        'socket': 'socket',
    }

    NETMASK_TYPE_MAP = {
        'ib': 'ib',
        'det': 'eth',
        'shm': 'eth',
        'socket': 'eth',
    }

    PINNING_OVERRIDE_METHOD = 'numactl'

    REMOTE_OPTION_TEMPLATE = ['--rsh=%(rsh)s']
    MPDBOOT_OPTIONS = []
    MPDBOOT_SET_INTERFACE = True

    MPIEXEC_TEMPLATE_GLOBAL_OPTION = ['-genv', '%(name)s', "%(value)s"]
    OPTS_FROM_ENV_TEMPLATE = ['-x', '%(name)s']
    MPIEXEC_OPTIONS = []

    MODULE_ENVIRONMENT_VARIABLES = ['MODULEPATH', 'LOADEDMODULES', 'MODULESHOME']

    OPTS_FROM_ENV_BASE = ['LD_LIBRARY_PATH', 'PATH', 'PYTHONPATH', 'CLASSPATH', 'LD_PRELOAD', 'PYTHONUNBUFFERED']
    OPTS_FROM_ENV_BASE_PREFIX = [
        'DAPL',
        'FI_PROVIDER',
        'IPATH',
        'KMP',
        'MKL',
        'O64',
        'OMP',
        'PSC',
        'PSM',
        'TMI',
        'VSMP',
        'UCX',
    ]
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

        self.pinning_override_type = getattr(self.options, 'overridepin', None)

        super(MPI, self).__init__(**kwargs)

        # sanity checks
        if getattr(self, 'sched_id', None) is None:
            self.log.raiseException("__init__: sched_id is None (should be set by one of the Sched classes)")

        if not self.cmdargs:
            self.log.raiseException("__init__: no executable or command provided")


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
        self.log.debug("main: going to execute cmd %s", " ".join(self.mpirun_cmd))
        self.log.info("writing mpirun output to %s", self.options.output)

        run_kwargs = {
            'fatal_no_output': self.options.output_check_fatal,
            'output_timeout': self.options.output_check_timeout,
        }
        if self.options.output:
            run_mpirun_cmd = RunFileLoopMPI.run
            run_kwargs['filename'] = self.options.output
        else:
            run_mpirun_cmd = RunAsyncMPI.run

        if self.options.dry_run:
            self.log.info("Dry run, only printing generated mpirun command...")
            print(' '.join(self.mpirun_cmd))
            exitcode = 0
        else:
            exitcode, _ = run_mpirun_cmd(self.mpirun_cmd, **run_kwargs)

        self.cleanup()

        if exitcode > 0:
            self.log.raiseException("main: exitcode %s > 0; cmd %s" % (exitcode, self.mpirun_cmd))

    ### BEGIN prepare ###
    def prepare(self):
        """Collect information to create the commands."""
        self.check_usable_cpus()
        self.check_limit()

        self.set_omp_threads()

        self.set_netmask()

        self.make_mpdboot_file()
        self.make_machine_file(universe=self.options.universe)

        self.set_pinning()

    def check_usable_cpus(self):
        """Check and log if non-standard cpus (eg due to cpusets)."""
        if not self.cores_per_node == len(self.cpus):
            self.log.info("check_usable_cpus: non-standard cpus found: found cpus %s, usable cpus %s",
                          self.cores_per_node, len(self.cpus))

    def check_limit(self):
        """Check if the softlimit of the stack exceeds 1MB, if it doesn't, show an error."""
        soft, _ = resource.getrlimit(resource.RLIMIT_STACK)  # in bytes
        if soft > -1 and soft < 1024 * 1024:
            # non-fatal
            self.log.error("Stack size %s%s too low? Increase with ulimit -s unlimited", soft, 'kB')

    def set_omp_threads(self):
        """
        Sets ompthreads to the amount of threads every MPI process should use.

        For example, with hybrid 2 every MPI process should have a total 2 threads (each on a seperate processor).
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
        exitcode, out = run(cmd)
        if exitcode > 0:
            self.log.raiseException("set_netmask: failed to run cmd '%s', ec: %s, out: %s" % (cmd, exitcode, out))

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
                    if len(self.nodes_uniq) > 1:
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

    def make_mpdboot_file(self):
        """
        Make an mpdbootfile.

        Parses the list of unique nodes and writes this information to a mpdbootfile
        (based on hydra and universe options).
        """
        self.make_mympirundir()

        if self.mpinodes is None:
            self.set_mpinodes()

        mpdboottxt = '\n'.join(nub(self.mpinodes))

        mpdfn = os.path.join(self.mympirundir, 'mpdboot')
        try:
            with open(mpdfn, 'w') as fp:
                fp.write(mpdboottxt)
        except IOError as err:
            msg = 'make_mpdboot_file: failed to write mpbboot file %s: %s' % (mpdfn, err)
            self.log.raiseException(msg)

        self.mpdboot_node_filename = mpdfn
        self.log.debug("make_mpdboot_file: wrote mpdbootfile %s:\n%s", mpdfn, mpdboottxt)

    def make_machine_file(self, nodetxt=None, universe=None):
        """
        Make the machinefile.

        Parses the list of nodes that run an MPI process and writes this information to a machinefile.
        """
        if not self.mympirundir:
            self.make_mympirundir()

        if self.mpinodes is None:
            self.set_mpinodes()

        if nodetxt is None:
            if universe is not None and universe > 0:
                universe_ppn = self.get_universe_ncpus()
                nodes = []
                for node in nub(self.mpinodes):
                    nodes.extend([node] * universe_ppn[node])
            else:
                nodes = self.mpinodes

            nodetxt = '\n'.join(nodes)

        nodefn = os.path.join(self.mympirundir, 'nodes')
        try:
            with open(nodefn, 'w') as fp:
                fp.write(nodetxt)
        except IOError as err:
            msg = 'make_machine_file: failed to write nodefile %s: %s' % (nodefn, err)
            self.log.raiseException(msg)

        self.mpiexec_node_filename = nodefn
        self.log.debug("make_machine_file: wrote nodefile %s:\n%s", nodefn, nodetxt)

    def get_universe_ncpus(self):
        """Construct dictionary with number of processes to start per node, based on --universe"""
        if self.options.universe > self.nodes_tot_cnt:
            ex = "Universe asks for more processes (%s) than available processors (%s)"
            self.log.raiseException(ex % (self.options.universe, self.nodes_tot_cnt))
        nodes = self.nodes_uniq[:]
        universe_ppn = dict((node, 0) for node in nodes)
        proc_cnt = 0
        node = nodes.pop(0)
        while proc_cnt < self.options.universe:
            if universe_ppn[node] < self.ppn_dict[node]:
                universe_ppn[node] += 1
                proc_cnt += 1
                # recycle node
                nodes.append(node)
            # select next node to assign a process to
            node = nodes.pop(0)
        return universe_ppn

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

        # add random 6-char salt to basepath
        randstr = ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(6))
        self.mympirunbasedir = os.path.join(basepath, '.mympirun_%s' % randstr)

        total_size = 0
        for dirpath, _, filenames in os.walk(self.mympirunbasedir):
            for filename in filenames:
                total_size += os.path.getsize(os.path.join(dirpath, filename))

        if total_size >= TEMPDIR_ERROR_SIZE:
            size_err = "the size of %s is currently %s, please clean it." % (self.mympirunbasedir, total_size)
            self.log.raiseException(size_err)
        elif total_size >= TEMPDIR_WARN_SIZE:
            self.log.warn("the size of %s is currently %s ", self.mympirunbasedir, total_size)

        destdir = os.path.join(self.mympirunbasedir, "%s_%s" % (self.sched_id, time.strftime("%Y%m%d_%H%M%S")))
        if not os.path.exists(destdir):
            try:
                os.makedirs(destdir)
            except os.error:
                self.log.raiseException('make_mympirun_dir: failed to make job dir %s' % destdir)

        self.log.debug("make_mympirun_dir: tmp mympirundir %s", destdir)
        self.mympirundir = destdir

    ### BEGIN pinning ###
    def set_pinning(self):
        """
        set pinmpi to True or False depending on the command line options 'pinmpi' and 'overridepin'

        When set to True, will disable the MPI flavor's native pinning method
        """

        # short circuit the call for self.options.pinmpi
        if not hasattr(self.options, 'pinmpi') or self.options.pinmpi is None:
            setattr(self.options, 'pinmpi', True)

        if self.pinning_override_type is not None:
            self.log.debug("set_pinning: overriding pin type to %s, pinmpi set to False", self.pinning_override_type)
            self.options.pinmpi = False
        else:
            self.log.debug("set_pinning: pinmpi %s", self.options.pinmpi)

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

            with open(mpdconffn, 'w') as mpdconff:
                mpdconff.write("password=%s" % ''.join(random.choice(string.ascii_uppercase + string.digits)
                                                       for x in range(10)))
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
        Get the localhost interfaces, based on the hostnames from the nodes in self.nodes_uniq.

        Raises Exception if no localhost interface was found.

        @return: the list of interfaces that correspond to the list of unique nodes
        """
        iface_prefix = ['eth', 'em', 'ib', 'wlan']
        reg_iface = re.compile(r'((?:%s)\d+(?:\.\d+)?(?::\d+)?|lo)' % '|'.join(iface_prefix))

        # iterate over unique nodes and get their interfaces
        # add the found interface to res if it matches reg_iface
        res = []
        for idx, nodename in enumerate(self.nodes_uniq):
            ip = socket.gethostbyname(nodename)
            cmd = "/sbin/ip -4 -o addr show to %s/32" % ip
            exitcode, out = run(cmd)
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
            self.log.raiseException("get_localhost: can't find localhost from nodes %s" % self.nodes_uniq)
        return res

    def make_mpdboot_options(self):
        """Add various options to mpdboot_options"""

        self.mpdboot_options = CmdList(*self.MPDBOOT_OPTIONS)

        # add the mpd nodefile to mpdboot options
        self.mpdboot_options.add("--file=%s" % self.mpdboot_node_filename)

        # add the interface to mpdboot options
        if self.MPDBOOT_SET_INTERFACE:
            if self.has_hydra:
                localmachine = self.mpdboot_localhost_interface[1]
                iface = ['-iface', localmachine]
            else:
                localmachine = self.mpdboot_localhost_interface[0]
                iface = ['--ifhn=%s' % localmachine]
            self.log.debug('Set mpdboot interface option "%s"', iface)
            self.mpdboot_options.add(iface)
        else:
            self.log.debug('No mpdboot interface option')

        # add the number of mpi processes (aka mpi universe) to mpdboot options
        if self.options.universe is not None and self.options.universe > 0 and not self.has_hydra:
            local_nodename = self.mpdboot_localhost_interface[0]
            self.mpdboot_options.add("--ncpus=%s" % self.get_universe_ncpus()[local_nodename])

        # set verbosity
        if self.options.mpdbootverbose:
            self.mpdboot_options.add("--verbose")

        # mpdboot rsh command
        if not self.has_hydra:
            self.mpdboot_options.add(self.REMOTE_OPTION_TEMPLATE, tmpl_vals={'rsh': self.get_rsh()})

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
        vars_to_pass = nub(filter(lambda key: key in os.environ, self.OPTS_FROM_ENV_BASE))
        self.mpiexec_opts_from_env.extend(vars_to_pass)

        prefixes = self.OPTS_FROM_ENV_FLAVOR_PREFIX + self.OPTS_FROM_ENV_BASE_PREFIX + self.options.variablesprefix
        for env_prefix in prefixes:
            for env_var in os.environ.keys():
                # add all environment variable keys that are equal to <prefix> or start with <prefix>_
                # to mpiexec_opts_from_env, but only if they aren't already in vars_to_pass
                if (env_prefix == env_var or env_var.startswith("%s_" % env_prefix)) and env_var not in vars_to_pass:
                    self.mpiexec_opts_from_env.append(env_var)

        self.log.debug("Vars passed: %s" % self.mpiexec_opts_from_env)

    def set_mpiexec_options(self):
        """Add various options to mpiexec_options."""
        self.mpiexec_options = CmdList(*self.MPIEXEC_OPTIONS)

        if self.has_hydra:
            self.make_mpiexec_hydra_options()
        else:
            self.mpiexec_options.add(['-machinefile', self.mpiexec_node_filename])

        # mpdboot global variables
        self.mpiexec_options.add(self.get_mpiexec_global_options())

        # number of procs to start
        if self.options.universe is not None and self.options.universe > 0:
            self.mpiexec_options.add(['-np', str(self.options.universe)])
        elif self.options.hybrid:
            num_proc = len(self.nodes_uniq) * self.options.hybrid * self.multiplier
            self.mpiexec_options.add(['-np', str(num_proc)])
        else:
            self.mpiexec_options.add(['-np', str(self.nodes_tot_cnt * self.multiplier)])

        # pass local env variables to mpiexec
        self.mpiexec_options.add(self.get_mpiexec_opts_from_env())

    def make_mpiexec_hydra_options(self):
        """Hydra specific mpiexec options."""
        self.get_hydra_info()
        # see https://software.intel.com/en-us/articles/controlling-process-placement-with-the-intel-mpi-library
        # --machinefile keeps the imbalance if there is one; --hostfile doesn't
        self.mpiexec_options.add(['--machinefile', self.mpiexec_node_filename])
        if self.options.branchcount is not None:
            self.mpiexec_options.add(['--branch-count', str(self.options.branchcount)])

        if getattr(self, 'HYDRA_RMK', None) is not None:
            rmk = [x for x in self.HYDRA_RMK if x in self.hydra_info.get('rmk', [])]
            if len(rmk) > 0:
                self.log.debug("make_mpiexec_hydra_options: HYDRA: rmk %s, using first", rmk)
                self.mpiexec_options.add(['-rmk', rmk[0]])
            else:
                self.log.debug("make_mpiexec_hydra_options: no rmk from HYDRA_RMK %s and hydra_info %s",
                               self.HYDRA_RMK, self.hydra_info)

        launcher = None
        default_launcher = getattr(self, 'HYDRA_LAUNCHER', None)
        avail_launchers = self.hydra_info.get('launcher', [])

        if self.options.launcher:
            launcher = self.options.launcher
            self.log.debug("Using specified launcher: %s", launcher)
            if launcher not in avail_launchers:
                err = "Specified launcher %s does not exist, available launchers: %s"
                self.log.warning(err % (launcher, avail_launchers))
        else:
            if default_launcher:
                self.log.debug("No launcher specified, using default launcher: %s" % default_launcher)
                launcher = default_launcher
            else:
                self.log.raiseException("There is no launcher specified, and no default launcher found")

        if launcher == RM_HYDRA_LAUNCHER:
            launcher = self.RM_HYDRA_LAUNCHER

        if not self.is_local():
            self.mpiexec_options.add(['-%s' % self.HYDRA_LAUNCHER_NAME, launcher])

        # when using ssh launcher, use custom pbsssh wrapper as exec
        if launcher == 'ssh':
            launcher_exec = getattr(self, 'HYDRA_LAUNCHER_EXEC', None)

            if launcher_exec is None:
                launcher_exec = self.get_rsh()

            if launcher_exec:
                self.log.debug("make_mpiexec_hydra_options: HYDRA using launcher exec %s", launcher_exec)
                self.mpiexec_options.add(['-%s-exec' % self.HYDRA_LAUNCHER_NAME, launcher_exec])
            else:
                self.log.debug("make_mpiexec_hydra_options: no launcher exec")

    def get_hydra_info(self):
        """Get a dict with hydra info."""
        reg_hydra_info = re.compile(r"^\s+(?P<key>\S[^:\n]*)\s*:(?P<value>.*?)\s*$", re.M)
        cmd = "mpirun -info"
        exitcode, out = run(cmd)
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
        opts = CmdList()

        for key, val in self.mpiexec_global_options.items():
            if key in self.mpiexec_opts_from_env:
                # environment variable is already set
                self.log.debug("get_mpiexec_global_options: found global option %s in mpiexec_opts_from_env.", key)
            else:
                # insert the keyvalue pair into the correct command line argument
                # the command for setting the environment variable depends on the mpi flavor
                opts.add(self.MPIEXEC_TEMPLATE_GLOBAL_OPTION, tmpl_vals={'name': key, "value": val})

        self.log.debug("get_mpiexec_global_options: template %s return options %s",
                       self.MPIEXEC_TEMPLATE_GLOBAL_OPTION, opts)
        return opts

    def get_mpiexec_opts_from_env(self):
        """
        gets the environment variables that should be passed to mpiexec as an option.

        Parses mpiexec_opts_from_env so that the chosen mpi flavor can understand it when it is passed to the
        command line argument.
        """

        opts = CmdList()
        self.log.debug("get_mpiexec_opts_from_env: variables (and current value) to pass: %s",
                       [[x, os.environ[x]] for x in self.mpiexec_opts_from_env])

        if '%(commaseparated)s' in self.OPTS_FROM_ENV_TEMPLATE:
            self.log.debug("get_mpiexec_opts_from_env: found commaseparated in template.")
            tmpl_vals = {'commaseparated': ','.join(self.mpiexec_opts_from_env)}
            opts.add(self.OPTS_FROM_ENV_TEMPLATE, tmpl_vals=tmpl_vals)
        else:
            for key in self.mpiexec_opts_from_env:
                opts.add(self.OPTS_FROM_ENV_TEMPLATE, tmpl_vals={'name': key, 'value': os.environ[key]})

        self.log.debug("get_mpiexec_opts_from_env: template %s return options %s", self.OPTS_FROM_ENV_TEMPLATE, opts)
        return opts

    ### BEGIN mpirun ###
    def make_mpirun(self):
        """Make the mpirun command (or whatever). It typically consists of a mpdboot and a mpiexec part."""

        self.mpirun_cmd = CmdList('mpirun')

        self._make_final_mpirun_cmd()
        if self.options.mpirunoptions is not None:
            self.mpirun_cmd.add(self.options.mpirunoptions.split(' '))
            self.log.debug("make_mpirun: added user provided options %s", self.options.mpirunoptions)

        if self.pinning_override_type is not None:
            self.mpirun_cmd.add(self.pinning_override())

        self.log.debug("make_mpirun: adding cmdargs %s", self.cmdargs)
        self.mpirun_cmd.add(self.cmdargs)

    def _make_final_mpirun_cmd(self):
        """
        Create the acual mpirun command.

        Append the mpdboot and mpiexec options to the command.
        """
        self.mpirun_cmd.add(self.mpdboot_options)
        self.mpirun_cmd.add(self.mpiexec_options)

    def pinning_override(self):
        """overriding the pinning method has to be handled by the flavor"""
        self.log.raiseException("pinning_override: not implemented.")

    def cleanup(self):
        """Remove temporary directory (mympirundir)"""
        try:
            shutil.rmtree(self.mympirundir)
            self.log.debug("cleanup: removed mympirundir %s", self.mympirundir)
        except OSError as err:
            self.log.raiseException("cleanup: cleaning up mympirundir %s failed: %s", self.mympirundir, err)
