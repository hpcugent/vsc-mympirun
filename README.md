# Description

`mympirun` is a tool to make it easier for usrs of HPC clusters to run MPI programs with good performance.

It wraps around the `mpiexec`/`mpirun`/... commands that are provided by the different MPI implementations (OpenMPI, Intel MPI, ...).

`mympirun` will determine the `mpirun` command to use, and takes into account the available resources to configure it.

Originally created by the [HPC team of Ghent University](http://ugent.be/hpc).


# License

`vsc-mympirun` is made available under the GNU General Public License
(GPL) version 2.


# Setup

Tune `vsc-mympirun` installation provides 'fake' `mpirun` commands to try and ensure that `mympirun` is always used.
These fake `mpirun` commands basically wrap around `mympirun` (which in turn wraps around the real `mpirun` command).

Therefore, you should make sure that the location of the `mympirun` command and the fake `mpirun` is prepended
to `$PATH`. If `mympirun` is provided via a module, you should load it *after* any other modules.


# Detection of MPI and job scheduler

`mympirun` detects which MPI implementation (OpenMPI, Intel MPI, ...) is being used, to figure out which `mpirun` command
it should be using. This can be overridden using the `--setmpi` or `-M` option. An overview of known MPI implementations
is available via `-m` or `--showmpi`.

In addition, the job scheduler (e.g., Torque) is also detected automatically, and can be overridden via `--schedtype` or `-S`.
If not job scheduler could be detected, local execution is assumed.
An overview of known job scheduler is available via `-s` or `--showsched`.


# Available resources

`mympirun` will detect the available resources, and pass options to the `mpirun` command benig used accordingly.

By default, it will use all avaiable cores, i.e.:

* all cores on the *current* system, if the `local` scheduler is used
* all cores assigned to the current job, if the `pbs` scheduler is used

This can be changed if needed using the `--hybrid`, `--universe`, `--double` or `--multi` options, see below.

Pinning of MPI processes to cores is also enabled by default (can be disabled using `--disable-pinmpi`).

It will also leverage the Torque integration of the MPI library being used by default, by launching MPI processes
using `pbsdsh` rather than `ssh`.


# Configuring `mympirun`

* `mympirun` command line options
* `$MYMPIRUN_*` environment variables
* configuration files (see `--configfiles`)

# Controlling number of processes

(explain briefly, include a clear example)

## `--hybrid` / `-h`

## `--universe`

## `--double` and `--multi`


# Controlling output

`--output`


# Passing down environemt variables

(explains default behavior, and how to tweak)

`--variablesprefix`


# Controlling launcher

`--launcher`

explain difference between `pbsdsh` and `ssh`


# Passing options to `mpirun`

`--mpirunoptions`

# Hang detection

(explains default behavior, and how to tweak)

`--output-check-timeout`, `--disable-output-check-fatal`

# Debugging

(use of `--debug`, `--logtofile`, `--debugmpi`)
