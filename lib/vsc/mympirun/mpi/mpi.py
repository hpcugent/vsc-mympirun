##
# Copyright 2009-2012 Stijn De Weirdt
#
# This file is part of VSC-tools,
# originally created by the HPC team of the University of Ghent (http://ugent.be/hpc).
#
#
# http://github.com/hpcugent/VSC-tools
#
# VSC-tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VSC-tools. If not, see <http://www.gnu.org/licenses/>.
##

"""
Base MPI class, all actual classes should inherit from this one
"""

from vsc.fancylogger import getLogger
from vsc.utils.run import run_simple, run_simple_noworries, run_to_file, run_async_to_stdout
from vsc.utils.IPy import IP

import os, re
import socket
import shutil
import time
import resource
import stat

## Going to guess myself

## part of the directory that contains the installed fakes
INSTALLATION_SUBDIRECTORY_NAME = 'mympirun'
## the fake subdir to contain the fake mpirun symlink
## also hardcoded in setup.py !
FAKE_SUBDIRECTORY_NAME = 'fake'

def get_subclasses(klass):
    """
    Get all subclasses recursively
    """
    res = []
    for cl in klass.__subclasses__():
        res.extend(get_subclasses(cl))
        res.append(cl)
    return res

def whatMPI(name):
    """
    Return the scriptname and the MPI class
    """
    fullscriptname = os.path.abspath(name)
    scriptname = os.path.basename(fullscriptname)

    found_mpi = get_subclasses(MPI)


    ## check on scriptname
    for mpi in found_mpi:
        if mpi._is_mpiscriptname_for(scriptname):
            stripfake() ## mandatory before return at this point
            return scriptname, mpi, found_mpi

    ## not called through alias
    ## stripfake is in which
    mpirunname = which(['mpirun'])
    if mpirunname is None:
        return None, None, found_mpi

    for mpi in found_mpi:
        if mpi._is_mpirun_for(mpirunname):
            return scriptname, mpi, found_mpi

    ## return found mpirunname
    return mpirunname, None, found_mpi


def _setenv(name, value):
    """Set environment variable. In principle os.environ should be sufficient."""
    os.putenv(name, "%s" % value)
    os.environ[name] = "%s" % value


def stripfake(path=None):
    """Remove the fake wrapper path:
        assumes mympirun/1.0.0/bin/fake
    """
    reg_fakepath = re.compile(r"" + os.sep.join(['.*?', INSTALLATION_SUBDIRECTORY_NAME + '.*?', 'bin',
                                                 FAKE_SUBDIRECTORY_NAME, '[^%s].*$' % os.sep]))

    if path is None:
        path = []
    envpath = os.environ.get('PATH', '').split(os.pathsep)
    ## do not append doubles (respect search order)
    path = envpath + [x for x in path if not x in envpath]

    newpath = [x for x in path if not reg_fakepath.match(x)]

    _setenv('PATH', ':'.join(newpath))

    return newpath

def which(names):
    """Find path to executable, similar to /usr/bin/which.
        @type names: list or string, returns first match.
    """
    if isinstance(names, str):
        names = [names]
    linuxdefaultpath = ['/usr/local/bin', '/usr/bin', '/usr/sbin', '/bin', '/sbin']

    newpath = stripfake(path=linuxdefaultpath)
    for seekName in names:
        for name in [os.path.join(p, seekName) for p in newpath]:
            if os.path.isfile(name):
                return name
    return None


## very basic class. has all the class method magic
class MPI(object):
    """
    Base MPI class to generate the mpirun command line
    """
    RUNTIMEOPTION = None

    _mpirun_for = []
    _mpiscriptname_for = []
    _mpirun_version = None

    MPIRUN_LOCALHOSTNAME = 'localhost'

    DEFAULT_RSH = None

    HYDRA = None
    HYDRA_LAUNCHER_NAME = "launcher"
    ## to be set in Sched subclasses, not here
    #HYDRA_RMK = None
    #HYDRA_LAUNCHER = 'ssh'
    #HYDRA_LAUNCHER_EXEC = None

    DEVICE_LOCATION_MAP = {'ib':'/dev/infiniband', 'det':'/dev/det', 'shm':'/dev/shm', 'socket':None}
    DEVICE_ORDER = ['ib', 'det', 'shm', 'socket']
    DEVICE_MPIDEVICE_MAP = {'ib':'rdma', 'det':'det', 'shm':'shm', 'socket':'socket'}

    NETMASK_TYPE_MAP = {'ib':'ib', 'det':'eth', 'shm':'eth', 'socket':'eth'}

    PINNING_OVERRIDE_METHOD = 'numactl'
    PINNING_OVERRIDE_TYPE_DEFAULT = None

    MPDBOOT_TEMPLATE_REMOTE_OPTION_NAME = "--rsh=%(rsh)s"

    MPIEXEC_TEMPLATE_GOBAL_OPTION = "-genv %(name)s %(value)s"
    MPIEXEC_TEMPLATE_LOCAL_OPTION = "-env %(name)s %(value)s"
    MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION = "-x %(name)s"

    GLOBAL_VARIABLES_ENVIRONMENT_MODULES = ['MODULEPATH', 'LOADEDMODULES', 'MODULESHOME']

    PASS_VARIABLES_BASE = ['LD_LIBRARY_PATH', 'PATH', 'PYTHONPATH', 'CLASSPATH', 'LD_PRELOAD', 'PYTHONUNBUFFERED']
    PASS_VARIABLES_BASE_PREFIX = ['OMP', 'MKL', 'KMP', 'DAPL', 'PSM', 'IPATH', 'TMI', 'PSC', 'O64', 'VSMP']
    PASS_VARIABLES_CLASS_PREFIX = [] ## to be set per derived class

    def __init__(self, options, cmdargs, **kwargs):
        if not hasattr(self, 'log'):
            self.log = getLogger(self.__class__.__name__)
        self.options = options
        self.cmdargs = cmdargs

        self.device = None

        self.hydra_info = None

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
        self.mpiexec_local_options = {}
        self.mpiexec_pass_environment = [] ## list of variables

        self.mpirun_cmd = None

        self.pinning_override_type = getattr(self.options, 'overridepin', self.PINNING_OVERRIDE_TYPE_DEFAULT)


        super(MPI, self).__init__(**kwargs)

        ## sanity checks
        if getattr(self, 'id', None) is None:
            self.log.raiseException("__init__: id None (should be set by one of the Sched classes)")

        if self.cmdargs is None or len(self.cmdargs) == 0:
            self.log.raiseException("__init__: no executable or command provided")

    ## factory methods for MPI
    # to add a new MPI class just create a new class that extends the cluster class
    # see http://stackoverflow.com/questions/456672/class-factory-in-python
    #classmethod
    def _is_mpirun_for(cls, name):
        """see if this class can provide support for found mpirun"""
        ## TODO report later in the initialization the found version
        reg = re.compile(r"(?:%s)%s(\d+(?:\.\d+(?:\.\d+\S+)?)?)" % ("|".join(cls._mpirun_for), os.sep))
        r = reg.search(name)
        if r:
            if cls._mpirun_version is None:
                return True
            else:
                ## do major,minor version check
                return cls._mpirun_version(r.group(1))
        else:
            return False

    _is_mpirun_for = classmethod(_is_mpirun_for)

    def _is_mpiscriptname_for(cls, name):
        """see if this class can provide support for scriptname"""
        return name in cls._mpiscriptname_for
    _is_mpiscriptname_for = classmethod(_is_mpiscriptname_for)


    ###
    # other general functionality
    #
    def _setenv(self, name, value):
        self.log.debug("_setenv; set name %s to value %s" % (name, value))
        _setenv(name, value)


    def cleanup(self):
        ## remove mympirundir
        try:
            shutil.rmtree(self.mympirundir)
            self.log.debug("cleanup: removed mympirundir %s" % self.mympirundir)
        except:
            self.log.raiseException("cleanup: cleaning up mympirundir %s failed" % (self.mympirundir))

    ### main ###
    def main(self):
        """Main method"""
        self.prepare()

        self.make_mpdboot()

        ## prepare these separately
        self.mpiexec_set_global_options()
        self.mpiexec_set_local_options()
        self.mpiexec_set_local_pass_variable_options()

        self.make_mpiexec()

        self.make_mpirun()

        ## actual execution
        for runfunc, cmd in self.mpirun_prepare_execution():
            ec, out = runfunc(cmd)
            if ec > 0:
                self.cleanup()
                self.log.raiseException("main: exitcode %s > 0; cmd %s" % (ec, cmd))
                break

        self.cleanup()

    ### BEGIN prepare ###
    def prepare(self):
        """Collect information to create the commands"""
        self.check_usable_cpus()
        self.check_limit()

        self.set_omp_threads()
        self.qlogic_ipath()
        self.scalemp_vsmp()

        self.set_netmask()

        self.make_node_file()

        self.set_pinning()

    def check_usable_cpus(self):
        """
        Check and act on fact of non-standard cpus (eg due to cpusets)
        - default: do nothing more then log
        """
        if not self.foundppn == len(self.cpus):
            self.log.info(("check_usable_cpus: non-standard cpus found: requested ppn %s, found cpus %s, "
                           "usable cpus %s") % (self.ppn, self.foundppn, len(self.cpus)))

    def check_limit(self):
        soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
        ## unit is kB
        if soft > -1 and soft < 1024 * 1024:
            ## non-fatal
            self.log.error("Stack size %s%s too low? Increase with ulimit -s unlimited" % (soft, 'kB'))

    def set_omp_threads(self):
        if 'OMP_NUM_THREADS' in os.environ:
            t = os.environ['OMP_NUM_THREADS']
        else:
            if self.options.hybrid is None or self.options.hybrid == 0:
                t = 1
            else:
                t = max(self.ppn // self.options.hybrid, 1)

        self.log.debug("Set OMP_NUM_THREADS to %s" % t)

        self._setenv('OMP_NUM_THREADS', t)

        setattr(self.options, 'ompthreads', t)


    def qlogic_ipath(self):
        """See if a qlogic device is available to set PSM parameters
            - at least one port in /ipathfs
        """
        setattr(self.options, 'qlogic_ipath', None)

        ipathpath = "/ipathfs/0"
        if os.path.isdir(ipathpath):
            self.global_vars['PSM_SHAREDCONTEXTS'] = '0'
            if self.options.debuglvl > 0:
                self.global_vars['PSM_TRACEMASK'] = '0x101'
            self.log.debug("qlogic_ipath: ipath found %s" % ipathpath)
            self.options.qlogic_ipath = True
        else:
            self.log.debug("qlogic_ipath: ipath path %s not found" % ipathpath)
            self.options.qlogic_ipath = False

    def scalemp_vsmp(self):
        """See if the node is using ScaleMP vSMP to set various parameters
            Detect vSMP presence + set additional default variables
            - vsmpctl --features works
            -- newer releases it is vsmpctl --status
        """
        setattr(self.options, 'scalemp_vsmp', None)

        vsmpctl = "vsmpctl --status"
        ec, out = run_simple_noworries(vsmpctl)
        if ec > 0:
            self.log.debug("scalemp_vsmp: vSMP not found (cmd %s ec %s output %s)" % (vsmpctl, ec, out))
            return

        """
        add /opt/ScaleMP/libvsmpclib/0.1/lib64/libvsmpclib.so to LD_PRELOAD
         - LD_PRELOAD is space separated
        """
        preload_lib = '/opt/ScaleMP/libvsmpclib/0.1/lib64/libvsmpclib.so'
        if os.path.exists(preload_lib):
            ## space separated list
            self._setenv('LD_PRELOAD', " ".join([preload_lib] + os.environ.get('LD_PRELOAD', '').split(" ")))

        if self.options.pinmpi:
            ## enable pinning
            if not 'VSMP_PLACEMENT' in os.environ:
                ## option: non, spread, nodes^x^y, packed
                if not self.foundppn == len(self.cpus):
                    self.log.debug(("scalemp_vsmp: non-standard cpus found: requested ppn %s, found ppn %s, "
                                    "usable cpus %s") % (self.ppn, self.foundppn, len(self.cpus)))
                    placement = []
                    for x in self.cpus:
                        ind = len(placement)
                        placement.append("%s:%s" % (ind, x))
                    self._setenv('VSMP_PLACEMENT', ",".join(placement))
                else:
                    self._setenv('VSMP_PLACEMENT', 'SPREAD')
            self.log.debug("scalemp_vsmp: vSMP VSMP_PLACEMENT set to %s" % os.environ['VSMP_PLACEMENT'])

            if not os.environ.has_key('VSMP_MEM_PIN'):
                self._setenv('VSMP_MEM_PIN', 'YES')
            self.log.debug("scalemp_vsmp: vSMP VSMP_MEM_PIN set to %s" % os.environ['VSMP_MEM_PIN'])
            ## add /opt/ScaleMP/numabind/bin to PATH
            numabindpath = '/opt/ScaleMP/numabind/bin'
            if os.path.exists(numabindpath):
                self._setenv('PATH', ":".join([numabindpath] + os.environ.get('PATH', '').split(":")))

        if self.options.debuglvl > 0:
            self._setenv('VSMP_VERBOSE', 1)

        self.log.debug("scalemp_vsmp: vSMP found %s with status" % out)

        self.options.scalemp_vsmp = True


    def set_device(self, force=False):
        if self.device is not None and not force:
            self.log.debug("set_device: device already set: %s" % self.device)
            return

        founddev = None
        if getattr(self.options, 'rdma', None):
            founddev = 'ib'
            self.device = 'rdma' ## force it
            path = self.DEVICE_LOCATION_MAP[founddev]
            if path is None or os.path.exists(path):
                self.log.warning("Forcing device %s (founddevice %s), but path %s not found." %
                                 (self.device, founddev, path))
        elif getattr(self.options, 'socket', None):
            founddev = 'socket'
            self.device = self.DEVICE_MPIDEVICE_MAP[founddev]
            path = self.DEVICE_LOCATION_MAP[founddev]
            if path is None or os.path.exists(path):
                self.log.warning("Forcing device %s (founddevice %s), but path %s not found." %
                                 (self.device, founddev, path))
        else:
            for dev in self.DEVICE_ORDER:
                if dev in ('shm',):
                    ## only for single node
                    if self.nruniquenodes > 1:
                        continue

                path = self.DEVICE_LOCATION_MAP[dev]
                if path is None or os.path.exists(path):
                    founddev = dev
                    self.device = self.DEVICE_MPIDEVICE_MAP[dev]
                    self.log.debug("set_device: found path %s for device %s" % (path, self.device))
                    break

        if self.device is None:
            self.log.raiseException("set_device: failed to set device.")

        self.netmasktype = self.NETMASK_TYPE_MAP[founddev]
        self.log.debug("set_device: set netmasktype %s for device %s (founddev %s)" %
                       (self.netmasktype, self.device, founddev))


    def set_netmask(self):
        if self.netmasktype is None:
            self.set_device()

        device_ip_reg_map = {'eth':"ether.*?\n.*?inet\s+(\d+\.\d+.\d+.\d+/\d+)",
                             'ib':"infiniband.*?\n.*?inet\s+(\d+\.\d+.\d+.\d+/\d+)"
                             }
        if not self.netmasktype in device_ip_reg_map:
            self.log.raiseException("set_netmask: can't get netmask for %s: unknown mode (device_ip_reg_map %s)" %
                                    (self.netmasktype, device_ip_reg_map))

        cmd = "/sbin/ip addr show"
        ec, out = run_simple(cmd)
        if ec > 0:
            self.log.raiseException("set_netmask: failed to run cmd %s: %s" % (cmd, out))

        reg = re.compile(r"" + device_ip_reg_map[self.netmasktype])
        if not reg.search(out):
            self.log.raiseException("set_netmask: can't get netmask for %s: no matches found (reg %s out %s)" %
                                    (self.netmasktype, device_ip_reg_map[self.netmasktype], out))

        res = []
        for ipaddr_mask in reg.finditer(out):
            ip = IP(ipaddr_mask.group(1), make_net=True)
            network_netmask = "%s/%s" % (ip.net(), ip.netmask())
            res.append(network_netmask)
            self.log.debug("set_netmask: convert ipaddr_mask %s into network_netmask %s" %
                           (ipaddr_mask.group(1), network_netmask))


        self.log.debug("set_netmask: return complete netmask %s" % res)
        if len(res) > 0:
            self.netmask = ":".join(res)


    def make_mympirundir(self):
        basepath = getattr(self.options, 'basepath', None)
        if basepath is None:
            basepath = os.environ['HOME']
        if not os.path.exists(basepath):
            self.log.raiseException("make_mympirun_dir: basepath %s should exist." % basepath)

        destdir = os.path.join(basepath, '.mympirun', "%s_%s" % (self.id, time.strftime("%Y%m%d_%H%M%S")))
        if not os.path.exists(destdir):
            try:
                os.makedirs(destdir)
            except:
                self.log.raiseException('make_mympirun_dir: failed to make job dir %s' % (destdir))

        self.log.debug("make_mympirun_dir: tmp mympirundir %s" % destdir)
        self.mympirundir = destdir

    def get_universe_ncpus(self):
        """Return ppn for universe"""
        return self.mpitotalppn

    def make_node_file(self):
        """Make the correct node list file"""
        self.make_mympirundir()

        if self.mpinodes is None:
            self.make_node_list()

        nodetxt = "\n".join(self.mpinodes + [''])

        mpdboottxt = ""
        for n in self.uniquenodes:
            txt = "%s" % n
            if not self.HYDRA:
                if self.options.universe is not None and self.options.universe > 0:
                    txt += ":%s" % self.get_universe_ncpus()
                txt += " ifhn=%s" % n

            mpdboottxt += "%s\n" % txt

        try:
            nodefn = os.path.join(self.mympirundir, 'nodes')
            file(nodefn, 'w').write(nodetxt)
            self.mpiexec_node_filename = nodefn
            self.log.debug("make_node_file: wrote nodefile %s:\n%s" % (nodefn, nodetxt))

            mpdfn = os.path.join(self.mympirundir, 'mpdboot')
            file(mpdfn, 'w').write(mpdboottxt)
            self.mpdboot_node_filename = mpdfn
            self.log.debug("make_node_file: wrote mpdbootfile %s:\n%s" % (mpdfn, mpdboottxt))
        except Exception:
            self.log.raiseException('make_node_file: failed to write nodefile %s mpbboot nodefile %s' %
                                    (nodefn, mpdfn))

    ### BEGIN pinning ###
    def _pin_flavour(self, mp=None):
        return mp

    def set_pinning(self, mp=None):
        if not hasattr(self.options, 'pinmpi'):
            setattr(self.options, 'pinmpi', None)

        mp = self._pin_flavour(mp)

        if isinstance(mp, bool):
            self.log.debug("set_pinning: setting pin_flavour %s" % mp)
            self.options.pinmpi = mp

        if not isinstance(self.options.pinmpi, bool):
            if self.options.hybrid is not None:
                ## always pin!
                self.options.pinmpi = True
            else:
                ## always pin!
                self.options.pinmpi = True

        if self.pinning_override_type is not None:
            self.log.debug("set_pinning: previous pinning %s;  will be overwritten, pinning_override_type set to %s" %
                           (self.options.pinmpi, self.pinning_override_type))
            self.options.pinmpi = False
        else:
            self.log.debug("set_pinning: pinmpi %s" % self.options.pinmpi)

    def get_pinning_override_variable(self):
        """
        Key element is that one needs to know the rank or something similar of each process
        - preferably in environment
        -- eg QLogic PSC_MPI_NODE_RANK: this instance is the nth local rank.
        - alternative is small c mpi program with bash wrapper

        -- see also likwid-mpirun for alternative example
        --- mentions similar OMPI_COMM_WORLD_RANK for OpenMPI and PMI_RANK for IntelMPI
        ---- local_rank is remainder of myrank diveded by number of nodes?

        This is a bash expression.
        - eg $((x/y)) is also fine
        """
        self.log.raiseException("get_pinning_override_variable: not implemented.")


    def pinning_override(self):
        """
        Create own pinning
        - using taskset or numactl?
        - start the real executable with correct pinning

        There are self.mpitotalppn number of processes to start
         on self.nruniquenodes * self.ppn requested slots
        Each node has to accept self.mpitotalppn/self.ppn processes
         over self.ppn nmber of cpu slots

        Do we assume heterogenous nodes (ie same cpu layuout as current node?)
        - yes
        -- reality NO: different cpusets!

        What do we support?
         - packed/compact : all together, ranks close to each other
         - spread: as far away as possible from each other
         - explicit map: TODO

        Option:
         - threaded (default yes): eg in hybrid, pin on all available cores or just one

        When in this mode, one needs to disable default/native pinning

        There seems no clean way to simply prefix the variables before the real exe
        - some mpirun are binary, others are bash
        -- no clean way to pass the variable
        --- a simple bash script also resolves the csh problem?
        """

        """
        Simple shell check. This is the login shell of the current user
        - not necessarily the current shell
        -- but it is when multinode is used i think (eg startup with ssh)
        """
        variableexpression = self.get_pinning_override_variable()
        if variableexpression is None:
            self.log.raiseException("pinning_override: no variable name found/set.")

        self.log.debug("pinning_override: using variable expression %s as local node rank." % variableexpression)

        rankname = 'MYMPIRUN_LOCALRANK'
        rankmapname = 'MYMPIRUN_LOCALRANK_MAP'

        wrappertxt = "#!/bin/bash\n%s=%s\n" % (rankname, variableexpression)

        ## number of local processors
        ## - eg nuamctl -s grep physcpubind
        if not self.ppn == self.foundppn:
            self.log.raiseException(("pinning_override: number of found procs %s is different from "
                                     "requested ppn %s. Not yet supported.") % (self.foundppn, self.ppn))

        override_type = self.pinning_override_type
        multithread = True
        if override_type.endswith('pin'):
            override_type = override_type[:-3]
            multithread = False
        self.log.debug("pinning_override: type %s multithread %s" % (override_type, multithread))

        """
        The whole method is very primitive
        - assume cpu layout on OS is correct wrt numbering

        What about pinned threads of threaded apps?
        - eg use likwid to pin those threads too.
        """

        ## cores per process
        corespp = self.foundppn // self.mpitotalppn
        corespp_rest = self.foundppn % self.mpitotalppn
        if (corespp < 1) or (self.mpitotalppn == self.foundppn):
            multi = False
            self.log.debug(("pinning_override: exactly one or more processes %s then cores %s. "
                            "No multithreading.") % (self.mpitotalppn, self.foundppn))
        if corespp_rest > 0:
            self.log.debug(("pinning_override: total number of mpiprocesses %s no exact multiple of "
                            "number of procs %s. Ignoring rest.") % (self.mpitotalppn, self.foundppn))


        map_func = None
        if override_type in ('packed', 'compact',):
            if multi:
                ## consecutive domains
                map_func = lambda x: "%s-%s" % (x * corespp, (x + 1) * corespp - 1)
            else:
                ## consecutive cores
                map_func = lambda x: "%s" % x
        elif override_type in ('cycle',):
            ## eg double with GAMESS
            if multi:
                ## what is this?
                self.log.raiseException("pinning_override: cycle type with multiple cores?")
            else:
                map_func = lambda x: "%s" % (x % self.foundppn)
        elif override_type in ('spread',):
            if multi:
                ## spread domains
                map_func = lambda x: "%s-%s" % (x * corespp, (x + 1) * corespp - 1)
            else:
                ## spread cores
                map_func = lambda x: "%s" % (x * corespp)

        else:
            self.log.raiseException("pinning_override: unsupported pinning_override_type  %s" %
                                    self.pinning_override_type)

        rankmap = [ map_func(x) for x in range(self.mpitotalppn)]


        wrappertxt += "%s=(%s)\n" % (rankmapname, ' '.join(rankmap))

        pinning_exe = which(self.PINNING_OVERRIDE_METHOD)
        if not pinning_exe:
            self.log.raiseException("pinning_override: can't find execuatble %s" % self.PINNING_OVERRIDE_METHOD)

        if self.PINNING_OVERRIDE_METHOD in ('numactl',):
            pinning_exe += ' --physcpubind="${%s[$%s]}"' % (rankmapname, rankname)

        wrappertxt += "%s $@" % pinning_exe
        wrapperpath = os.path.join(self.jobdir, 'pinning_override_wrapper.sh')
        try:
            open(wrapperpath, 'w').write(wrappertxt)
            os.chmod(wrapperpath, stat.S_IRWXU)
            self.log.debug("pinning_override: wrote wrapper file %s:\n%s" % (wrapperpath, wrappertxt))
        except:
            self.log.raiseException('pinning_override: failed to write wrapper file %s' % (wrapperpath))

        self.log.debug("pinning_override: pinning_exe %s to wrapper %s" % (pinning_exe, wrapperpath))

        return wrapperpath


    ### BEGIN mpdboot ###
    def make_mpdboot(self):
        """Make the mpdboot configuration"""
        # check .mpd.conf existence
        mpdconffn = os.path.join(os.environ['HOME'], '.mpd.conf')
        if not os.path.exists(mpdconffn):
            self.log.raiseException(("make_mpdboot: mpd.conf file not found at %s. Create this file "
                                     "(text file with minimal entry 'password=<somesecretpassword>')") % mpdconffn)

        self.mpdboot_set_localhost_interface()

        self.make_mpdboot_options()

        self.log.debug("make_mpdboot set options %s" % self.mpdboot_options)


    def make_mpdboot_options(self):
        """Make the mpdboot options. Customise this method."""
        ## the mpdboot options
        self.mpdboot_options = []

        ## uniq hosts with ifhn for mpdboot start
        self.mpdboot_options.append("--file=%s" % self.mpdboot_node_filename)

        ## mpdboot ifhn
        if self.HYDRA:
            iface = "-iface %s" % self.mpdboot_localhost_interface[1]
        else:
            iface = "--ifhn=%s" % self.mpdboot_localhost_interface[0]
        self.mpdboot_options.append(iface)

        if self.options.universe is not None and self.options.universe > 0:
            self.mpdboot_options.append("--ncpus=%s" % self.get_universe_ncpus())

        ## number of mpi
        if self.mpdboot_totalnum:
            self.mpdboot_options.append("--totalnum=%s" % self.mpdboot_totalnum)

        ## verbosity
        if self.options.mpdbootverbose:
            self.mpdboot_options.append("--verbose")

        ## mpdboot rsh command
        if not self.HYDRA:
            self.mpdboot_options.append(self.MPDBOOT_TEMPLATE_REMOTE_OPTION_NAME % { 'rsh' : self.get_rsh()})

    def mpdboot_set_localhost_interface(self):
        """
        Get the localhost mpdboot interface
        -- if hostname is different from the name in the nodelist
        """
        iface_prefix = ['eth', 'em', 'ib', 'wlan']
        reg_iface = re.compile(r'((?:%s)\d+(?:\.\d+)?(?::\d+)?|lo)' % '|'.join(iface_prefix))

        for hn in self.uniquenodes:
            ip = socket.gethostbyname(hn)
            cmd = "/sbin/ip -4 -o addr show to %s/32" % ip ## TODO ipv6
            ec, out = run_simple(cmd)
            if ec == 0:
                r = reg_iface.search(out)
                if not r:
                    self.log.raiseException(("mpdboot_set_localhost_interface: no interface match for "
                                             "prefixes %s out %s") % (iface_prefix, out))
                iface = r.group(1)
                self.log.debug("set_mpd_localhost_interface: mpd localhost interface %s found for %s (ip: %s)" %
                               (iface, hn, ip))
                self.mpdboot_localhost_interface = (hn, iface)
                return
        self.log.raiseException("set_mpd_localhost_interface: can't find mpd localhost from uniq nodes %s" %
                                (self.uniquenodes))

    ### BEGIN mpiexec ###
    def make_mpiexec(self):
        """Make the mpiexec configuration"""
        self.make_mpiexec_options()

        self.log.debug("make_mpiexec set options %s" % self.mpiexec_options)



    def make_mpiexec_options(self):
        """The mpiexec options"""
        self.mpiexec_options = []

        if self.HYDRA:
            self.make_mpiexec_hydra_options()
        else:
            self.mpiexec_options.append("-machinefile %s" % self.mpiexec_node_filename)

        ## mpdboot global variables
        self.mpiexec_options += self.mpiexec_get_global_options()

        ## number of procs to start
        if self.options.universe is not None and self.options.universe > 0:
            self.mpiexec_options.append("-np %s" % self.options.universe)
        else:
            self.mpiexec_options.append("-np %s" % (self.mpitotalppn * self.nruniquenodes))

        ## mpdboot local variables
        self.mpiexec_options += self.mpiexec_get_local_options()

        ## pass local env variables
        self.mpiexec_options += self.mpiexec_get_local_pass_variable_options()

    def make_mpiexec_hydra_options(self):
        """Hydra specific mpiexec options"""
        self.get_hydra_info()
        self.mpiexec_options.append("-f %s" % self.mpiexec_node_filename)

        ## default launcher seems ssh
        if getattr(self, 'HYDRA_RMK', None) is not None:
            rmk = [x for x in self.HYDRA_RMK if x in self.hydra_info.get('rmk', [])]
            if len(rmk) > 0:
                self.log.debug("make_mpiexe_hydra_options: HYDRA: rmk %s, using first" % rmk)
                self.mpiexec_options.append("-rmk %s" % rmk[0])
            else:
                self.log.debug("make_mpiexe_hydra_options: no rmk from HYDRA_RMK %s and hydra_info %s" %
                               (self.HYDRA_RMK, self.hydra_info))
        else:
            launcher = None
            if getattr(self, 'HYDRA_LAUNCHER', None) is not None:
                launcher = [x for x in self.HYDRA_LAUNCHER if x in self.hydra_info.get('launcher', [])]
                if len(launcher) > 0:
                    self.log.debug("make_mpiexec_hydra_options: HYDRA: launcher %s, using first one" % launcher)
                else:
                    self.log.debug("make_mpiexe_hydra_options: no launcher from HYDRA_LAUNCHER %s and hydra_info %s" %
                                   (self.HYDRA_LAUNCHER, self.hydra_info))

            launcher_exec = self.HYDRA_LAUNCHER_EXEC
            if launcher is None or len(launcher) == 0:
                launcher_exec = self.get_rsh()
            else:
                self.mpiexec_options.append("-%s %s" % (self.HYDRA_LAUNCHER_NAME, launcher[0]))

            if launcher_exec is not None:
                self.log.debug("make_mpiexec_hydra_options: HYDRA using launcher exec %s" % launcher_exec)
                self.mpiexec_options.append("-%s-exec %s" % (self.HYDRA_LAUNCHER_NAME, launcher_exec))

    def get_hydra_info(self):
        """Get a dict with hydra info"""
        reg_hydra_info = re.compile(r"^\s+(?P<key>\S[^:\n]*)\s*:(?P<value>.*?)\s*$", re.M)

        cmd = "mpirun -info"
        ec, out = run_simple(cmd)
        if ec > 0:
            self.log.raiseException("get_hydra_info: failed to run cmd %s: %s" % (cmd, out))

        hydra_info = {}
        for r in reg_hydra_info.finditer(out):
            key = r.groupdict()['key']
            if key is None:
                self.log.raiseException("get_hydra_info: failed to get hydra info: missing key in %s (out: %s)" %
                                        (r.groupdict(), out))
            key = key.strip().lower()
            value = r.groupdict()['value']
            if value is None:
                self.log.debug("get_hydra_info: failed to get hydra info: missing value in %s (out: %s)" %
                               (r.groupdict(), out))
                value = ''
            values = [x.strip().strip('"').strip("'") for x in value.split() if len(x.strip()) > 0]
            hydra_info[key] = values
        self.log.debug("get_hydra_info: found info %s" % hydra_info)

        keymap = {"rmk":r'^resource\s+management\s+kernel.*available',
                  "launcher":r'^%s.*available' % self.HYDRA_LAUNCHER_NAME,
                  "chkpt":r'^checkpointing.*available',
                  }
        self.hydra_info = {}
        for newkey, regtxt in keymap.items():
            reg = re.compile(regtxt, re.I)
            matches = [v for k, v in hydra_info.items() if reg.search(k)]
            if len(matches) == 0:
                continue
            else:
                if len(matches) > 1:
                    self.log.warning(("get_hydra_info: more then one match %s found for newkey %s "
                                      "regtxt %s hydrainfo %s") % (matches, newkey, regtxt, hydra_info))
                self.hydra_info[newkey] = matches[0]

        self.log.debug("get_hydra_info: filtered info %s" % self.hydra_info)


    def mpiexec_set_global_options(self):
        """Set mpiexec global options"""
        self.mpiexec_global_options['MKL_NUM_THREADS'] = '1'

        if not self.options.noenvmodules:
            for env_var in self.GLOBAL_VARIABLES_ENVIRONMENT_MODULES:
                if env_var in os.environ and not env_var in self.mpiexec_global_options:
                    self.mpiexec_global_options[env_var] = os.environ[env_var]


    def mpiexec_set_local_options(self):
        """Set mpiexec local options"""

    def mpiexec_set_local_pass_variable_options(self):
        """Set mpiexec pass variables"""
        for env_var in self.PASS_VARIABLES_BASE:
            if env_var in os.environ and not env_var in self.mpiexec_pass_environment:
                self.mpiexec_pass_environment.append(env_var)

        for env_prefix in self.PASS_VARIABLES_CLASS_PREFIX + self.PASS_VARIABLES_BASE_PREFIX + self.options.variablesprefix:
            for env_var in os.environ.keys():
                ## exact match or starts with <prefix>_
                if (env_prefix == env_var or env_var.startswith("%s_" % env_prefix)) and not env_var in self.mpiexec_pass_environment:
                    self.mpiexec_pass_environment.append(env_var)


    def mpiexec_get_global_options(self):
        """Create the global options to pass through mpiexec
            allow overwriting through environment
        """
        global_options = []

        for k, v in self.mpiexec_global_options.items():
            if k in self.mpiexec_pass_environment:
                self.log.debug("mpiexec_get_global_options: found global option %s in mpiexec_pass_environment." % k)
            else:
                global_options.append(self.MPIEXEC_TEMPLATE_GOBAL_OPTION % {'name':k, "value":v})

        self.log.debug("mpiexec_get_global_options: template %s return options %s" %
                       (self.MPIEXEC_TEMPLATE_GOBAL_OPTION, global_options))
        return global_options

    def mpiexec_get_local_options(self):
        """Create the local options to pass through mpiexec
            allow overwriting through environment
        """
        local_options = []
        for k, v in self.mpiexec_local_options.items():
            if k in self.mpiexec_pass_environment:
                self.log.debug("mpiexec_get_local_options: found local option %s in mpiexec_pass_environment." % k)
            else:
                local_options.append(self.MPIEXEC_TEMPLATE_LOCAL_OPTION % {'name':k, "value":v})

        self.log.debug("mpiexec_get_local_options: templates %s return options %s" %
                       (self.MPIEXEC_TEMPLATE_LOCAL_OPTION, local_options))
        return local_options

    def mpiexec_get_local_pass_variable_options(self):
        """Create the local options to pass environment vaiables through mpiexec
        """
        self.log.debug("mpiexec_get_local_pass_variable_options: variables (and current value) to pass: %s" %
                       ([ [x, os.environ[x]] for x in self.mpiexec_pass_environment]))

        if '%(commaseparated)s' in self.MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION:
            self.log.debug("mpiexec_get_local_pass_variable_options: found commaseparated in template.")
            local_pass_options = [self.MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION %
                                  {'commaseparated': ','.join(self.mpiexec_pass_environment)}]
        else:
            local_pass_options = [self.MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION %
                                  {'name':x, 'value':os.environ[x]} for x in self.mpiexec_pass_environment]

        self.log.debug("mpiexec_get_local_pass_variable_options: template %s return options %s" %
                       (self.MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION, local_pass_options))
        return local_pass_options


    ### BEGIN mpirun ###

    def make_mpirun(self):
        """Make the mpirun command (or whatever). It typically consists of a mpdboot and a mpiexec part"""

        self.mpirun_cmd = ['mpirun']

        self._make_final_mpirun_cmd()
        if self.options.mpirunoptions is not None:
            self.log.debug("make_mpirun: added user provided options %s" % self.options.mpirunopts)
            self.mpirun_cmd.append(self.options.mpirunopts)

        if self.pinning_override_type is not None:
            p_o = self.pinning_override()
            if p_o is None or not os.path.isfile(p_o):
                self.log.raiseException("make_mpirun: no valid pinning_overrride %s (see previous errors)" % p_o)
            else:
                self.mpirun_cmd += [p_o]

        ## the executable
        self.mpirun_cmd += self.cmdargs

    def _make_final_mpirun_cmd(self):
        """Create the acual mpirun command
            add it to self.mpirun_cmd
        """
        self.mpirun_cmd += self.mpdboot_options
        self.mpirun_cmd += self.mpiexec_options

    def mpirun_prepare_execution(self):
        """
        Make a list of tuples to start the actual mpirun command
            list of tuples
                (run_function_to_run, cmd)
        """
        def main_runfunc(cmd):
            if self.options.output is not None:
                return run_to_file(cmd, filename=self.options.output)
            else:
                return run_async_to_stdout(cmd)

        return [(main_runfunc, " ".join(self.mpirun_cmd))]
