import numpy as np
from tqdm import tqdm

if __name__ == "__main__":
    #Import radio
    # from terra_dsp.DataSource.iio import PlutoSource
    # from terra_dsp.DataSource.uhd import USRPSource
    from terra_dsp.DataSource.soapy import SoapySource

    #Set up recording
    FREQUENCY_SAMPLING = 4e6
    FREQUENCY_CENTER = 105.1e6
    samples = int(72e6)

    ds = SoapySource(fs=FREQUENCY_SAMPLING, fc=FREQUENCY_CENTER, chunk_length=24000000)
    # ds = PlutoSource(fs=FREQUENCY_SAMPLING, fc=FREQUENCY_CENTER, uri=None, chunk_length=24000000)
    # ds = USRPSource(fs=fs, fc=fc, chunk_length=24000000)

    samples_array = np.zeros(samples, dtype=np.complex64)
    for i in tqdm(range(3)):
        while(not ds.samples_available()):
            pass
        samples_array[24000000*i:24000000*(i+1)] = ds.get_chunk()/100

    ds.stop()
    del ds
    #save
    print(samples_array)
    samples_array.astype(np.complex64).tofile('rec.raw')