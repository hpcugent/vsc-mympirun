# Description

Python libraries interfacing different mpi implementations.

Originally created by the [HPC team of Ghent University](http://ugent.be/hpc).

# License

`vsc-mympirun` is made available under the GNU General Public License
(GPL) version 2.


# Workflow

The first step of mympirun is making sure that every mpirun command passes
through mympirun. This is accomplished by prepending a fake mpirun path to
`$PATH`, which will catch the attempt to execute mpirun and forward it to
mympirun.

Next, the script will import every MPI flavor implementation from
`lib/vsc/mympirun/mpi`. This way it is possible to deduce the MPI flavor that
is requested by observing the path of the executable that called mympirun.

It will follow the same process for determining the scheduler. Both MPI flavor
and scheduler flavor can be overwritten by using the `-M` and `-S` options
respectively.

Once both flavors have been set, the script will get some standard MPI
configuration variables, such as usable nodes, netmask,... It will handle CPU
pinning if enabled.

After setting up, it will transform the command line arguments and other global
environment variables to a dict with options that the chosen MPI flavor can
understand.

Finally, it passes these options to the correct mpirun executable of the
selected MPI flavor.
