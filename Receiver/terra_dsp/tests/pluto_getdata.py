import numpy as np 
import adi
from terra_dsp.DataSource.iio import get_uri

if __name__ == "__main__":
    fs = int(6e6)
    fc = int(105.3e6)

    sdr = adi.Pluto(uri=get_uri())
    sdr.rx_rf_bandwidth = fs
    sdr.sample_rate = fs
    sdr.rx_lo = fc
    sdr.rx_enabled_channels = [0]
    sdr.gain_control_mode_chan0 = "manual"
    gain = 50.0
    sdr.rx_output_type = 'raw'
    sdr.rx_hardwaregain_chan0 = gain
    sdr.rx_buffer_size = 10000

    num_samples = 0
    shared_memory_index = 0
    samples = sdr.rx()

    print(samples.shape)
    print(samples)