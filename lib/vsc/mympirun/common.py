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
Common between mpi and pmi
"""
import os
import re
import sys

from vsc.utils.fancylogger import getLogger
from distutils.version import LooseVersion
from vsc.utils.missing import get_subclasses

LOGGER = getLogger()

# part of the directory that contains the installed fakes
INSTALLATION_SUBDIRECTORY_NAME = '(VSC-tools|(?:vsc-)?mympirun)'
# the fake subdir to contain the fake mpirun symlink
# also hardcoded in setup.py !
FAKE_SUBDIRECTORY_NAME = 'fake'


def eb_root_version(name):
    """
    Return EBROOT and EBVERSION for name

    Returns (None, None) on failure, (EBROOT, EBVERSION) otherwise
    """

    res = []
    for var in ['root', 'version']:
        var_name = 'EB%s%s' % (var.upper(), name.upper())
        if var_name in os.environ:
            res.append(os.environ.get(var_name))
        else:
            LOGGER.debug("$%s not defined for %s", var_name, name)
            return (None, None)

    return tuple(res)


def filtered_subclasses(klass):
    # exclude Coupler classes which also is a subclass of mpi/sched, since it's not an actual mpi/scheduler
    return [c for c in get_subclasses(klass) if not c.HIDDEN]


def what_sched(requested, schedm):
    """Return the scheduler class """

    def sched_to_key(klass):
        """Return key for specified scheduler class which can be used for sorting."""
        # use lowercase class name for sorting
        key = klass.__name__.lower()
        # prefix key for SLURM scheduler class with '_'
        #   this is done to consider SLURM before PBS,
        #   since $PBS* environment variables may be defined in SLURM job env
        if key == 'slurm':
            key = '_' + key

        return key

    # exclude Coupler classes which also is a subclass of Sched, since it's not an actual scheduler
    found_sched = sorted(filtered_subclasses(schedm.Sched), key=sched_to_key)

    # Get local scheduler
    local_sched = get_local_sched(found_sched)

    # first, try to use the scheduler that was requested
    if requested:
        for sched in found_sched:
            if sched._is_sched_for(requested):
                return sched, found_sched
        LOGGER.warn("%s scheduler was requested, but mympirun failed to find an implementation", requested)

    # next, try to use the scheduler defined by environment variables
    for sched in found_sched:

        # determine whether environment variable for node info (like $PBS_NODEFILE, $SLURM_NODELIST) is defined;
        if hasattr(sched, 'SCHED_ENVIRON_NODE_INFO'):
            # take into account that SCHED_ENVIRON_NODE_INFO can be None,
            # and checking "None in os.environ" fails hard in Python 3 (string value is required)
            nodeinfo = (sched.SCHED_ENVIRON_NODE_INFO or '') in os.environ
        else:
            # if SCHED_ENVIRON_NODE_INFO attribute does not exist, we still check SCHED_ENVIRON_ID below
            nodeinfo = True

        if nodeinfo:
            # determine whether environment variable that specifies job ID (like $PBS_JOBID, $SLURM_JOBID) is defined
            if (getattr(sched, 'SCHED_ENVIRON_ID', None) or '') in os.environ:
                return sched, found_sched

    # If that fails, try to force the local scheduler
    LOGGER.debug("No scheduler found in environment, trying local")
    return local_sched, found_sched


def get_local_sched(found_sched):
    """Helper function to get local scheduler (or None, if there is no local scheduler)"""
    res = None
    for sched in found_sched:
        if sched._is_sched_for("local"):
            res = sched
            break
    return res


def what_mpi(name, mpi_klass):
    """
    Return the path of the selected mpirun and its class.

    @param name: The name of the executable used to run mympirun

    @return: A triplet containing the following variables:
      - The path to the executable used to run mympirun (should be the path to an mpirun implementation)
      - The corresponding python class of the MPI variant
      - The python classes of the supported MPI flavors (from the various .py files in mympirun/mpi)
    """

    # supported MPI implementations
    #   The coupler is also a subclass of MPI, but it isn't and MPI implementation
    supp_mpi_impl = filtered_subclasses(mpi_klass)

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
        if mpi._is_mpiscriptname_for(scriptname) and mpi._is_mpirun_for(mpirun_path):
            LOGGER.debug("%s was used to call mympirun", scriptname)
            return scriptname, mpi, supp_mpi_impl

    # mympirun was not called through a known alias, so find out which MPI
    # implementation the user has installed
    for mpi in supp_mpi_impl:
        if mpi._is_mpirun_for(mpirun_path):
            return scriptname, mpi, supp_mpi_impl

    # no specific flavor found, default to mpirun_path
    LOGGER.warn("The executable that called mympirun (%s) isn't supported, defaulting to %s", name, mpirun_path)
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


def version_in_range(version, lower_limit, upper_limit):
    """
    Check whether version is in specified range

    :param lower_limit: lower limit for version (inclusive), no lower limit if None
    :param upper_limit: upper limit for version (exclusive), no upper limit if None
    """
    in_range = True
    if lower_limit is not None and LooseVersion(version) < LooseVersion(lower_limit):
        in_range = False
    if upper_limit is not None and LooseVersion(version) >= LooseVersion(upper_limit):
        in_range = False
    return in_range


class SchedBase(object):

    _sched_for = []  # classname is default added
    _sched_environ_test = []
    SCHED_ENVIRON_ID = None

    HIDDEN = False

    # factory methods for Sched. To add a new Sched class just create a new class that extends the cluster class
    # see http://stackoverflow.com/questions/456672/class-factory-in-python
    @classmethod
    def _is_sched_for(cls, name=None):
        """see if this class can provide support for sched class"""
        if name is not None:
            # add class name as default
            return name in cls._sched_for + [cls.__name__]

        # guess it from environment
        totest = cls._sched_environ_test
        if cls.SCHED_ENVIRON_ID is not None:
            totest.append(cls.SCHED_ENVIRON_ID)

        for envvar in totest:
            envval = os.environ.get(envvar, None)
            if not envval:
                continue
            else:
                return True

        return False


class MpiBase(object):

    _mpirun_for = None
    _mpiscriptname_for = []
    _mpirun_version = None

    HIDDEN = False
    RUNTIMEOPTION = None

    # factory methods for MPI
    @classmethod
    def _is_mpirun_for(cls, mpirun_path):
        """
        Check if this class provides support for active mpirun command.

        @param cls: the class that calls this function
        @return: True if mpirun is located in $EBROOT*, and if $EBVERSION* value matches version requirement
        """
        res = False

        mpiname = cls._mpirun_for
        if mpiname:
            LOGGER.debug("Checking whether %s (MPI name: %s) matches %s", cls, mpiname, mpirun_path)

            # first, check whether specified mpirun location is in $EBROOT<NAME>
            mpiroot, mpiversion = eb_root_version(mpiname)
            if mpiroot:
                LOGGER.debug("found mpi root: %s", mpiroot)
                # try to determine resolved path for both, this may file if we hit a non-existing paths
                try:
                    mpirun_path_real = os.path.realpath(mpirun_path)
                    mpiroot = os.path.realpath(mpiroot)
                except (IOError, OSError) as err:
                    LOGGER.debug("Failed to resolve paths %s and %s, ignoring it: %s", mpirun_path, mpiroot, err)

                # only if mpirun location is in $EBROOT* location, we should check the version too
                if mpirun_path.startswith(mpiroot) or mpirun_path_real.startswith(mpiroot):
                    LOGGER.debug("%s (real %s) is in subdirectory of %s", mpirun_path, mpirun_path_real, mpiroot)

                    # next, check if version meets requirements (checked via _mpirun_version function)

                    # mympirun is not compatible with OpenMPI version 2.0: this version contains a bug
                    # see https://github.com/hpcugent/vsc-mympirun/issues/113
                    if mpiname == "OpenMPI" and version_in_range(mpiversion, "2.0", "2.1"):
                        LOGGER.error(("OpenMPI 2.0.x uses a different naming protocol for nodes. As a result, it isn't "
                                      "compatible with mympirun. This issue is not present in OpenMPI 1.x and it has "
                                      "been fixed in OpenMPI 2.1 and further."))
                        sys.exit(1)

                    mpirun_version_check = getattr(cls, '_mpirun_version', None)
                    if mpirun_version_check and mpiversion:
                        res = mpirun_version_check(mpiversion)
                        LOGGER.debug("found mpirun version %s match for %s: %s", mpiversion, cls, res)
                    elif mpirun_version_check is None:
                        LOGGER.debug("no mpirun version provided, skipping version check, match for %s" % cls)
                        res = True
                    else:
                        LOGGER.debug("mpi version not found, not match for %s", cls)
                else:
                    LOGGER.debug("%s (real %s) is not in subdirectory of %s, no match for %s",
                                 mpirun_path, mpirun_path_real, mpiroot, cls)
            else:
                LOGGER.debug("mpi root not defined, no match for %s", cls)

        return res

    @classmethod
    def _is_mpiscriptname_for(cls, scriptname):
        """
        Check if this class provides support for scriptname.

        @param cls: the class that calls this function
        @param scriptname: the executable that called mympirun

        @return: true if $scriptname is defined as an mpiscriptname of $cls
        """

        return scriptname in cls._mpiscriptname_for
