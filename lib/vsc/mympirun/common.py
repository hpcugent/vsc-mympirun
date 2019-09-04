#
# Copyright 2011-2019 Ghent University
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

from vsc.utils.fancylogger import getLogger
from distutils.version import LooseVersion
from vsc.utils.missing import get_subclasses

LOGGER = getLogger()

# part of the directory that contains the installed fakes
INSTALLATION_SUBDIRECTORY_NAME = '(VSC-tools|(?:vsc-)?mympirun)'
# the fake subdir to contain the fake mpirun symlink
# also hardcoded in setup.py !
FAKE_SUBDIRECTORY_NAME = 'fake'


def what_sched(requested, schedm):
    """Return the scheduler class """

    def sched_to_key(klass):
        """Return key for specified scheduler class which can be used for sorting."""
        # use lowercase class name for sorting
        key = klass.__name__.lower()
        # prefix key for SLURM scheduler class with '_'
        # this is done to consider SLURM before PBS, since $PBS* environment variables may be defined in SLURM job env
        if key == 'slurm':
            key = '_' + key

        return key

    # exclude Coupler class which also is a subclass of Sched, since it's not an actual scheduler
    found_sched = sorted([c for c in get_subclasses(schedm.Sched) if c.__name__ != 'Coupler'], key=sched_to_key)

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
        if sched.SCHED_ENVIRON_NODE_INFO in os.environ and sched.SCHED_ENVIRON_ID in os.environ:
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

    # The coupler is also a subclass of MPI, but it isn't and MPI implementation
    supp_mpi_impl = [x for x in get_subclasses(mpi_klass) if x.__name__ != 'Coupler']  # supported MPI implementations

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


