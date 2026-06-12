import numpy as np
import pyopencl as cl
import scipy.signal as sg

kernel_src = """
#define PI 3.14159265358979323846f

__kernel void freq_shift(
    __global const float *input_real,
    __global const float *input_imag,
    __global       float* out_real,
    __global       float* out_imag,
    float f_bb,
    float fs,
    float stime,
    int   n)
{
    int i = get_global_id(0);
    if (i >= n) return;

    long phase_num = ((long)i * (long)(f_bb)) % (long)(fs);
    float phase = (float)phase_num / fs;  // now in [0, 1), exact
    float angle = -2.0f * PI * phase;
    float cs, sn;
    sn = sincos(angle, &cs);           // compute both at once

    float2 lo  = (float2)(cs, sn);     // e^(-j*angle)
    float2 sig = (float2)(input_real[i], input_imag[i]);

    // complex multiply: (a+jb)(c+jd) = (ac-bd) + j(ad+bc)
    out_real[i] = sig.x * lo.x - sig.y * lo.y;
    out_imag[i] = sig.x * lo.y + sig.y * lo.x;
    //out_real[i] = cs;
    //out_imag[i] = sn;
}
"""

resample_kernel_src = """
__kernel void polyphase_resample(
    __global const float *input_real,
    __global const float *input_imag,
    __global       float2* out,
    __global const float*  taps,
    int n_in,
    int n_out,
    int n_taps,
    int down)
{
    int i = get_global_id(0);
    if (i >= n_out) return;

    int base = i * down + (n_taps - 1) / 2;  // shift by group delay
    float2 acc = (float2)(0.0f, 0.0f);
    for (int k = 0; k < n_taps; k++) {
        int idx = base - k;
        if (idx >= 0 && idx < n_in) {
            acc.x += input_real[idx] * taps[k];
            acc.y += input_imag[idx] * taps[k];
        }
    }
    out[i] = acc;
}
"""

def freq_shift_filter_gpu(raw_data, f_bb, fs, stime, ctx=None, queue=None, kernels=None, rate=15):
    """Frequency-shifts a complex IQ signal to baseband and decimates it using a GPU. 

    :param raw_data: Input IQ samples.
    :type raw_data: array-like complex
    :param f_bb: 
    :type f_bb:
    :param f_bb: Baseband frequency offset in Hz.
    :type f_bb: float
    :param fs: sample rate.
    :type fs: float
    :param stime: Block start time. Not currently used
    :type stime: float
    :param ctx: Existing OpenCL context. Created from first available platform if None.
    :type ctx: cl.Context, optional
    :param queue: Existing command queue. Created from ctx if None.
    :type queue: cl.CommandQueue, optional
    :param kernels: Pre-compiled kernels. Compiled on first call if None.
    :type kernels: list[cl.Kernel], optional
    :param rate: Integer decimation factor. Defaults to 15.
    :type rate: int, optional

    :return: Decimated, frequency shifted IQ data.
    :rtype: np.ndarray, dtype=complex64
    """

    if(ctx is None):
        platform = cl.get_platforms()[0]
        device = platform.get_devices()[0]
        ctx = cl.Context([device])
    if(queue is None):
        queue = cl.CommandQueue(ctx)

    if(kernels is None):
        kernels = [cl.Program(ctx, kernel_src).build().freq_shift,
                     cl.Program(ctx, resample_kernel_src).build().polyphase_resample]

    data_real = np.real(raw_data).astype(np.float32)
    data_imag = np.imag(raw_data).astype(np.float32)

    real_buf  = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=data_real)
    imag_buf  = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=data_imag)

    out_real = np.zeros(len(raw_data), dtype=np.float32)
    out_imag = np.zeros(len(raw_data), dtype=np.float32)

    out_real_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, out_real.nbytes)
    out_imag_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, out_imag.nbytes)

    kernels[0].set_args(
        real_buf, imag_buf, 
        out_real_buf, out_imag_buf,
        np.float32(f_bb), np.float32(fs),
        np.float32(stime), np.int32(len(raw_data))
    )
    global_size = (len(raw_data) + 256,)
    local_size  = None

    cl.enqueue_nd_range_kernel(queue, kernels[0], global_size, local_size)
    # queue.finish()
    # cl.enqueue_copy(queue, out_real, out_real_buf)
    # cl.enqueue_copy(queue, out_imag, out_imag_buf)
    # end = time.time()
    # print(f'Frequency Shift: {end - start}')

    # freq_shifted_gpu = out_real + 1j*out_imag
    # return sg.resample_poly(freq_shifted_gpu, 1,15)

    # print(np.allclose(freq_shifted_gpu, freq_shifted_samps, atol=1e-3, rtol=1e-3))

    up, down = 1, rate
    n_taps = 2 * 10 * down + 1

    fir = sg.firwin(n_taps, 1.0 / down, window=('kaiser', 5.0)).astype(np.float32)
    n = len(raw_data)
    n_out = int(np.ceil(n / down))

    filt_out = np.zeros(n_out * 2, dtype=np.float32)
    out_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, filt_out.nbytes)

    fir_gpu = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=fir)

    kernels[1](queue, (n_out,), None,
        out_real_buf, out_imag_buf, out_buf, fir_gpu,
        np.int32(n), np.int32(n_out), np.int32(len(fir)), np.int32(down))

    cl.enqueue_copy(queue, filt_out, out_buf)
    queue.finish()

    return filt_out.view(np.complex64)

def get_gpu_channelizer_kernel(ctx):
    """Compiles and returns the two OpenCL kernels used by freq_shift_filter_gpu. 
    Call once per context and cache the result to avoid repeated JIT compilation. 

    :param ctx: An initialized OpenCL context targeting the desired device.
    :type ctx: cl.Context

    :return: [freq_shift_kernel, polyphase_resample_kernel]
    :rtype: list[cl.Kernel]
    """    
    return [cl.Program(ctx, kernel_src).build().freq_shift, 
            cl.Program(ctx, resample_kernel_src).build().polyphase_resample]

def gpu_arbfreq_channelizer(data, freqs, fs, stime, ctx=None, queue=None, kernels=None, rate=15):
    """Runs freq_shift_filter_gpu over a list of arbitrary center frequencies, 
    returning one decimated baseband channel per frequency. Channels are processed sequentially. 

    :param data: Wideband input IQ block.
    :type data: array-like complex
    :param freqs: Center frequencies to extract (Hz). One output channel per entry.
    :type freqs: list[float]
    :param fs: Input sample rate.
    :type fs: float
    :param stime: Start time of block in seconds.
    :type stime: float 
    :param ctx: OpenCL context, created if None. Defaults to None.
    :type ctx: cl.Context, optional
    :param queue: Command queue. Not used. Defaults to None.
    :type queue: cl.CommandQueue, optional
    :param kernels: Pre-compiled kernels; see get_gpu_channelizer_kernel. Defaults to None.
    :type kernels: list[cl.Kernel], optional
    :param rate: Decimation factor. Defaults to 15.
    :type rate: int, optional

    :return: 2D array of baseband data with shape (len(freqs), (N/rate))
    :rtype: np.ndarray, dtype=complex64
    """    
    return np.array([freq_shift_filter_gpu(data, 
                                  freq, 
                                  fs, 
                                  stime, 
                                  ctx=ctx, 
                                  queue=None, 
                                  kernels=kernels, rate=rate) for freq in freqs])

def freq_shift_filter_cpu(raw_data, f_bb, fs, stime, rate = 15):
    """Pure NumPy/SciPy reference implementation of a single-channel frequency shift and 
    decimation. Generates a time vector from stime, multiplies by the complex LO, 
    then calls scipy.signal.resample_poly for 1:rate downsampling. Useful for validation 
    against the GPU path. 

    :param raw_data: Input IQ samples.
    :type raw_data: array-like complex
    :param f_bb: Frequency offset to shift to baseband (Hz).
    :type f_bb: float
    :param fs: Input sample rate (Hz).
    :type fs: float
    :param stime: Absolute start time of block. Used to compute LO phase.
    :type stime: float
    :param rate: Decimation factor. Defaults to 15.
    :type rate: int, optional

    :return: Decimated baseband data.
    :rtype: np.ndarray, dtype=complex64
    """    
    t = np.arange(len(raw_data)) / fs + stime
    lo = np.exp(-1j*2*np.pi*f_bb*t).astype(np.complex64)
    freq_shifted_samps = raw_data * lo
    
    return sg.resample_poly(freq_shifted_samps, 1,rate).astype(np.complex64)

def cpu_arbfreq_channelizer(data, freqs, fs, stime, rate = 15):
    """Runs freq_shift_filter_cpu over a list of arbitrary center frequencies, 
    returning one decimated baseband channel per frequency. Channels are processed sequentially. 

    :param data: Wideband input IQ block.
    :type data: array-like complex
    :param freqs: Center frequencies to extract (Hz). One output channel per entry.
    :type freqs: list[float]
    :param fs: Input sample rate.
    :type fs: float
    :param stime: Start time of block in seconds.
    :type stime: float
    :param rate: Decimation factor. Defaults to 15.
    :type rate: int, optional

    :return: 2D array of baseband data with shape (len(freqs), (N/rate))
    :rtype: np.ndarray, dtype=complex64
    """     
    return np.array([freq_shift_filter_cpu(data, freq, fs, stime, rate) for freq in freqs])

def get_pfb_channelizer(taps, channels, channel_mask):
    """Returns a closure that wraps pfb_channelizer with pre-bound taps, 
    channels, and channel_mask arguments. The returned callable has the 
    signature (data, freqs, fs, stime), making it a drop-in replacement 
    for the arbitrary-frequency channelizers, though freqs, fs, and 
    stime are ignored by the PFB implementation. 

    :param taps: Polyphase filter bank taps, one row per channel. Typically produced by compute_pfb_channelizer.
    :type taps: np.ndarray
    :param channels: Number of uniform frequency channels (FFT size).
    :type channels: int
    :param channel_mask: Indices of channels to return from the full FFT output.
    :type channel_mask: array-like int

    :return: PFB channelizing function.
    :rtype: callable(data, freqs, fs, stime) -> np.ndarray
    """    
    return lambda data, freqs, fs, stime: pfb_channelizer(data, taps, channels, channel_mask)

def compute_pfb_channelizer(chunk_length, ntaps, channels):
    """Designs the prototype low-pass filter for a uniform 
    polyphase filter bank and returns the per-channel tap matrix. 
    The stopband transition width is set to 0.02 / channels 
    (as a fraction of the Nyquist rate) around each channel 
    edge. The filter is designed with scipy.signal.remez (equiripple), 
    then reshaped into a (channels, ntaps // channels) matrix with 
    columns reversed for convolution ordering. 

    :param chunk_length: Length of each input data chunk. Not used.
    :type chunk_length: int
    :param ntaps: Total number of prototype filter taps. Should be a multiple of channels.
    :type ntaps: int
    :param channels: Number of output channels.
    :type channels: int

    :return: polyphase tap matrix
    :rtype: np.ndarray
    """    
    clearance = 0.02/channels #fraction of each band to use for transition
    bands = [0, 0.5/channels-clearance, 0.5/channels+clearance, 0.5]
    # shift = 0.5 / channels - clearance/2
    # bands = [0, shift - clearance, shift + clearance, 0.5]
    taps_1d = sg.remez(ntaps, bands, [1,0])#* np.exp(2j * np.pi * shift * np.arange(ntaps))
    taps = taps_1d.reshape(-1, channels).T
    return taps[:, ::-1]

def pfb_channelizer(data, taps, channels, channel_mask):    
    """ Implements a uniform polyphase filter bank channelizer. 
    The input is zero-padded by the filter group delay, split 
    into channels polyphase branches, each branch is filtered 
    with its corresponding row of taps via scipy.signal.lfilter, 
    then a per-branch phase correction is applied before an FFT 
    collapses the branches into channels uniform frequency bins. 
    Only the bins indexed by channel_mask are returned. 

    :param data: Wideband input IQ block. Length should be a multiple of channels after padding.
    :type data: np.ndarray
    :param taps: Polyphase tap matrix from compute_pfb_channelizer.
    :type taps: np.ndarray
    :param channels: Number of frequency channels / FFT size.
    :type channels: int
    :param channel_mask: Indices into the full FFT output selecting which channels to return.
    :type channel_mask: array-like int

    :return: Complex channel outputs.
    :rtype: np.ndarray
    """    
    delay = (taps.shape[1] - 1) // 2
    data = np.concatenate([data, np.zeros(delay * channels)])
    polydata = data.reshape(-1, channels).T
    fdata = np.array([sg.lfilter(taps[i], [1], polydata[i]) for i in range(channels)])
    fdata = fdata[:, delay:]
    for k in range(channels):
        fdata[k] *= np.exp(-2j * np.pi * k / channels)
    all_channels = np.fft.fft(fdata, axis=0)
    return all_channels[channel_mask]