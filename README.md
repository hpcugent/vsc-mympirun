# Description

`mympirun` is a tool to make it easier for usrs of HPC clusters to run MPI programs with good performance.

It wraps around the `mpiexec`/`mpirun`/... commands that are provided by the different MPI implementations (OpenMPI, Intel MPI, ...).

`mympirun` will determine the `mpirun` command to use, and takes into account the available resources to configure it.

Originally created by the [HPC team of Ghent University](http://ugent.be/hpc).


# License

`vsc-mympirun` is made available under the GNU General Public License (GPL) version 2.


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


# Setup

Tune `vsc-mympirun` installation provides 'fake' `mpirun` commands to try and ensure that `mympirun` is always used.
These fake `mpirun` commands basically wrap around `mympirun` (which in turn wraps around the real `mpirun` command).

Therefore, you should make sure that the location of the `mympirun` command and the fake `mpirun` is prepended to `$PATH`. If `mympirun` is provided via a module, you should load it *after* any other modules.


# Detection of MPI and job scheduler

`mympirun` detects which MPI implementation (OpenMPI, Intel MPI, ...) is being used, to figure out which `mpirun` command it should be using. This can be overridden using the `--setmpi` or `-M` option. An overview of known MPI implementations is available via `-m` or `--showmpi`.

In addition, the job scheduler (e.g., Torque) is also detected automatically, and can be overridden via `--schedtype` or `-S`.
If not job scheduler could be detected, local execution is assumed.
An overview of known job scheduler is available via `-s` or `--showsched`.


# Available resources

`mympirun` will detect the available resources, and pass options to the `mpirun` command being used accordingly.

By default, it will use all available cores, i.e.:

* all cores on the *current* system, if the `local` scheduler is used
* all cores assigned to the current job, if the `pbs` scheduler is used

This can be changed if needed using the `--hybrid`, `--universe`, `--double` or `--multi` options, see below.

Pinning of MPI processes to cores is also enabled by default (can be disabled using `--disable-pinmpi`).

It will also leverage the Torque integration of the MPI library being used by default, by launching MPI processes using `pbsdsh` rather than `ssh`.


# Configuring `mympirun`

* `mympirun` command line options
* `$MYMPIRUN_*` environment variables
* configuration files (see `--configfiles`)

# Controlling number of processes

## `--hybrid` / `-h`
The `hybrid` or `h` option requires one integer. This integer will be the number of processes started on each available physical node.
        
    $ echo $PBS_NUM_NODES
    2

    $ mympirun --hybrid 2 hostname
    node2157.delcatty.os
    node2157.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os

## `--universe`
The `universe`option also requires one integer. This integer will be the exact number of processes started by mympirun (independent of the number of nodes). When using `universe` for multiple processes, mympirun will try to balance the processes on the available nodes.
        
    $ echo $PBS_NUM_NODES
    2

    $ mympirun --universe 1 hostname
    node2157.delcatty.os
    

## `--double` and `--multi`
As the name suggests, when using the `double` option,  mympirun will start double the amount of processes as requested. The `multi`option works the same but it requires an integer, indicating the multiplier, for example, `multi 3` will start triple the amount of processes. This means `double` and `multi 2` will have the exact same effect.

    $ echo $PBS_NUM_NODES
    2

    $ echo $PBS_NUM_PPN
    4

    $ mympirun --double hostname
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    


# Controlling output

Use `--output` to redirect your mympirun output to a file instead of stdout/stderr. 

    $ mympirun --output out.txt hostname
    
    $ cat out.txt
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2157.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    node2158.delcatty.os
    


# Passing down environment variables

The environment variables that mympirun passes to the MPI environment are `LD_LIBRARY_PATH`, `PATH`, `PYTHONPATH`, `CLASSPATH`, `LD_PRELOAD`, `PYTHONUNBUFFERED` and all environment variables that are prefixed with `OMP`, `MKL`, `KMP`, `DAPL`, `PSM`, `IPATH`, `TMI`, `PSC`, `O64`, and `VSMP`

To add other variables to this list, you can use the mympirun option  `--variablesprefix`. This option requires a comma-seperated list of strings that are either the exact variable name or a prefix that matches the environment variable(s).

    $ mypmirun ./echo_my_env_var
    
    $ export MY_ENV_VAR="my_env_var"
    $ mympirun --variablesprefix MY_ENV ./echo_my_env_var
    my_env_var
    my_env_var


# Controlling launcher

In recent Intel MPI versions (> 4.1), mpirun uses Hydra as its process manager. It is possible to change the launcher Hydra uses using the `--launcher` option. 

explain difference between `pbsdsh` and `ssh`


# Passing options to `mpirun`

To pass options directly to the mpirun command, use `--mpirunoptions`. This option is used with a string of options, which is then appended to the mpirun command generated by mympirun.  

Options to be used with Intel MPI can be found in the [Command Reference](https://software.intel.com/en-us/node/528769) section of the Intel MPI documentation. For options with OpenMPI, check the [mpirun man page](https://www.open-mpi.org/doc/v1.8/man1/mpirun.1.php).



# Hang detection

If your mpi jobscript doesn't have any output for a long time, mympirun will assume something is wrong and will interrupt your job as a safety measure (we wouldn't want your program to "hang" for hours, or even days, without really doing anything).  The default time mympirun waits for output is one hour (3600 seconds).

You can change the amount of time mympirun waits for output by using the option `output-check-timeout` with a number of seconds, or you can disable it alltogether by using the option `--disable-output-check-fatal`.

# Debugging

To get all debugging info from mympirun itself, use the option `--debug` or simply `-d`. This will print to stdout by default. 

For debugging on MPI level, use `--debugmpi`.

Redirecting the logger output of a mympirun script to a file is done with the option `--logtofile`. 
