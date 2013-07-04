import numpy as np
import pyopencl as cl
import quantities as q
from syris.gpu import util as gpu_util
from syris import config as cfg
from unittest import TestCase


class TestPropagator(TestCase):

    def setUp(self):
        self.ctx = gpu_util.get_cuda_context()
        self.queue = gpu_util.get_command_queues(self.ctx)[0]
        src = gpu_util.get_source(["vcomplex.cl", "propagation.cl"])
        self.prg = cl.Program(self.ctx, src).build()
        self.size = 256
        self.mem = cl.Buffer(self.ctx, cl.mem_flags.READ_WRITE,
                             size=self.size ** 2 * cfg.CL_CPLX)
        self.distance = 1 * q.m
        self.lam = 4.9594e-11 * q.m
        self.pixel_size = 1 * q.um

    def _execute_kernel(self, phase_factor=0 + 0j):
        res = np.empty((self.size, self.size), dtype=cfg.NP_CPLX)
        self.prg.propagator(self.queue,
                            (self.size, self.size),
                            None,
                            self.mem,
                            cfg.NP_FLOAT(self.distance.simplified),
                            cfg.NP_FLOAT(self.lam.simplified),
                            cfg.NP_FLOAT(self.pixel_size.simplified),
                            gpu_util.make_vcomplex(phase_factor))
        cl.enqueue_copy(self.queue, res, self.mem)

        return res

    def _cpu_propagator(self, phase_factor=1):
        j, i = np.mgrid[-0.5:0.5:1.0 / self.size, -0.5:0.5:1.0 / self.size].\
            astype(cfg.NP_FLOAT)

        return cfg.NP_CPLX(phase_factor) * \
            np.fft.fftshift(np.exp(- np.pi * self.lam.simplified *
                                   self.distance.simplified *
                                   (i ** 2 + j ** 2) /
                                   self.pixel_size.simplified ** 2 * 1j))

    def _compare(self, im_0, im_1):
        real = np.abs(im_0.real - im_1.real)
        imag = np.abs(im_0.imag - im_1.imag)

        return real[np.where(real > 1e-5)].shape == (0,) and \
            imag[np.where(imag > 1e-5)].shape == (0,)

    def test_no_phase_factor(self):
        res = self._execute_kernel()
        cpu = self._cpu_propagator()

        self.assertTrue(self._compare(res, cpu))

    def test_with_phase_factor(self):
        phase = np.exp(2 * np.pi / self.lam.simplified *
                       self.distance.simplified * 1j)

        res = self._execute_kernel(phase)
        cpu = self._cpu_propagator(phase)

        self.assertTrue(self._compare(res, cpu))