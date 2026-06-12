import unittest
import numpy as np
import pyopencl as cl
import matplotlib.pyplot as plt
import time
from terra_dsp.channelizer import freq_shift_filter_cpu, freq_shift_filter_gpu, get_gpu_channelizer_kernel, cpu_arbfreq_channelizer, gpu_arbfreq_channelizer

class TestAccelerators(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        platform = cl.get_platforms()[0]
        device = platform.get_devices()[0]
        self.ctx = cl.Context([device])
        self.queue = cl.CommandQueue(self.ctx)

        self.channelizer_kernel = get_gpu_channelizer_kernel(self.ctx)

        super(TestAccelerators, self).__init__(*args, **kwargs)
        
    def testsucceed_fsf_gpu(self):
        f_bb = 1.6e6
        fs = 6e6
        rng = np.random.default_rng(42)
        samples = (rng.standard_normal(24000000) + 1j * rng.standard_normal(24000000))/10
        samples_cpu = freq_shift_filter_cpu(samples, f_bb, fs, 0)
        print(samples_cpu)
        samples_gpu = freq_shift_filter_gpu(samples, f_bb, fs, 0, self.ctx, self.queue,self.channelizer_kernel)
        print(samples_gpu)
        self.assertTrue(np.allclose(samples_cpu,
                                samples_gpu,
                                rtol=1e-5, atol=1e-5))
    
    def testfail_fsf_gpu(self):
        f_bb = 1.6e6
        fs = 6e6
        rng = np.random.default_rng(11)
        samples = (rng.standard_normal(500000) + 1j * rng.standard_normal(500000))/10
        self.assertFalse(np.allclose(freq_shift_filter_cpu(samples, f_bb, fs, 0),
                                freq_shift_filter_gpu(samples, f_bb, fs, 0, self.ctx, self.queue,self.channelizer_kernel),
                                rtol=1e-30, atol=1e-30))
        
    def testsucceed_arb_freq_gpu(self):
        f_bb = [200e3, 400e3, 2e6, 1.6e6]
        fs = 6e6
        rng = np.random.default_rng(11)
        samples = (rng.standard_normal(24000000) + 1j * rng.standard_normal(24000000))/10
        channels_cpu = cpu_arbfreq_channelizer(samples, f_bb, fs, 0)
        print(channels_cpu)
        channels_gpu = gpu_arbfreq_channelizer(samples, f_bb, fs, 0, self.ctx, self.queue, self.channelizer_kernel)
        print(channels_gpu)
        # tf = plt.figure()
        # plt.plot(np.)
        self.assertTrue(np.allclose(channels_cpu, channels_gpu, rtol=1e-5, atol=1e-5))

    def testsucceed_pfb_cpu(self):
        from terra_dsp.channelizer import compute_pfb_channelizer, get_pfb_channelizer
        f_bb = [-400e3, 800e3, 1.6e6, -1.2e6]
        fs = 4e6
        ntaps = 60*15
        channel_width = 400e3
        channels = round(fs/channel_width) 
        channel_freqs = np.roll(np.arange(-fs//2 + channel_width//2, fs//2, channel_width), channels//2)
        print(channel_freqs)
        clen = 240000

        channel_mask = []
        for i in range(len(f_bb)):
            channel_idx = np.where(channel_freqs == f_bb[i])[0]
            if(len(channel_idx)) != 1:
                raise ValueError("Invalid channel")
            channel_mask.append(channel_idx[0])

        taps = compute_pfb_channelizer(clen, ntaps, 15)
        channelizer = get_pfb_channelizer(taps, channels, channel_mask)

        rng = np.random.default_rng(11)
        samples = (rng.standard_normal(clen) + 1j * rng.standard_normal(clen))/10
        channels_cpu = cpu_arbfreq_channelizer(samples, f_bb, fs, 0)

        channels_pfb = channelizer(samples, f_bb, fs, 0)

        self.assertTrue(np.allclose(channels_cpu, channels_pfb, atol=0.05, rtol=0.1))

if __name__ == '__main__':
    unittest.main()