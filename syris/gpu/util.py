"""
Utility functions concerning GPU programming.
"""

import pyopencl as cl
from pyopencl.array import vec
import time
from syris import profiling as prf
from syris import config as cfg
from syris.opticalelements import graphicalobjects as gro
import logging
import os


LOGGER = logging.getLogger(__name__)

_SINGLE_HEADER = """
typedef float vfloat;
typedef float2 vfloat2;
typedef float3 vfloat3;
typedef float4 vfloat4;
typedef float8 vfloat8;
typedef float16 vfloat16;

"""

_DOUBLE_HEADER = """
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
typedef double vfloat;
typedef double2 vfloat2;
typedef double3 vfloat3;
typedef double4 vfloat4;
typedef double8 vfloat8;
typedef double16 vfloat16;

"""


def get_source(file_names, precision_sensitive=True):
    """Get source by concatenating files from *file_names* list and apply
    single or double precision parametrization if *precision_sensitive*
    is True.
    """
    string = ""
    for file_name in file_names:
        path = os.path.join(os.path.dirname(__file__),
                            cfg.KERNELS_FOLDER, file_name)
        string += open(path, "r").read()

    if precision_sensitive:
        header = _SINGLE_HEADER if cfg.single_precision() else _DOUBLE_HEADER
        string = header + string

    return string


def get_metaobjects_source():
    """Get source string for metaobjects creation."""
    obj_types = _object_types_to_struct()
    source = get_source(["polyobject.cl", "heapsort.cl",
                         "newtonraphson.cl", "metaobjects.cl"])

    return obj_types + source


def _object_types_to_struct():
    string = "typedef enum _OBJECT_TYPE {"
    for i in range(len(gro.OBJECT_TYPES) - 1):
        string += gro.OBJECT_TYPES[i] + ","
    string += gro.OBJECT_TYPES[len(gro.OBJECT_TYPES) - 1]
    string += "} OBJECT_TYPE;"

    return string


def execute(function, *args, **kwargs):
    """Execute a *function* which can be an OpenCL kernel or other OpenCL
    related function and profile it.
    """
    event = function(*args, **kwargs)
    if function.__class__ == cl.Kernel:
        func_name = function.function_name
    else:
        func_name = function.__name__

    prf.PROFILER.add(event, func_name)

    return event


def get_cuda_platform(platforms):
    """Get the NVIDIA CUDA platform if any."""
    for plat in platforms:
        if plat.name == "NVIDIA CUDA":
            return plat
    return None


def get_cuda_devices():
    """Get all CUDA devices."""
    return get_cuda_platform(cl.get_platforms()).get_devices()


def get_cuda_context(devices=None, properties=None):
    """Create an NVIDIA CUDA context with *properties* for *devices*,
    if None are given create the context for all available."""
    if devices is None:
        devices = get_cuda_platform(cl.get_platforms()).get_devices()

    LOGGER.debug("Creating OpenCL context for %d devices." % (len(devices)))
    start = time.time()
    ctx = cl.Context(devices, properties)
    LOGGER.debug("OpenCL context created in %g s." % (time.time() - start))

    return ctx


def get_command_queues(context, devices=None,
                       queue_args=(), queue_kwargs={}):
    """Create command queues for each of the *devices* within a specified
    *context*. If *devices* is None, NVIDIA GPUs are automatically
    detected and used for creating the command queues.
    """
    if devices is None:
        devices = get_cuda_devices()

    LOGGER.debug("Creating %d command queues." % (len(devices)))
    queues = []
    for device in devices:
        queues.append(cl.CommandQueue(context, device,
                                      *queue_args, **queue_kwargs))

    LOGGER.debug("%d command queues created." % (len(devices)))

    return queues


def _make_vfloat_functions():
    """Make functions for creating OpenCL vfloat data types from host
    data types. Follow PyOpenCL make_floatn and make_doublen convention
    and use them for implementation.
    """
    def _wrapper(i):
        def make_vfloat(*args):
            if cfg.single_precision():
                return getattr(vec, "make_float%d" % (i))(*args)
            else:
                return getattr(vec, "make_double%d" % (i))(*args)
        make_vfloat.__name__ = "make_vfloat%d" % (i)
        return make_vfloat

    for i in [2, 3, 4, 8, 16]:
        globals()[_wrapper(i).__name__] = _wrapper(i)

_make_vfloat_functions()


def make_vcomplex(value):
    """Make complex value for OpenCL based on the set floating point
    precision.
    """
    return make_vfloat2(value.real, value.imag)
