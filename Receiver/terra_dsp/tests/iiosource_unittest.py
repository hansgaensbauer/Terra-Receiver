import unittest
from terra_dsp.DataSource.iio import PlutoSource
import scipy.signal as sg
from tqdm import tqdm, trange
import time
import numpy as np

class TestPluto(unittest.TestCase):

    def test_getdata(self):
                
        FREQUENCY_SAMPLING = 6e6
        FREQUENCY_CENTER = 94.5e6

        us = PlutoSource(FREQUENCY_SAMPLING, FREQUENCY_CENTER, None, 6000000)
        print('Got source')
        while(not us.samples_available()):
            pass

        chunk = us.get_chunk()        
        print("Got chunk")
        del us
        self.assertTrue(len(chunk) == 6000000)

    def test_rate(self):
                
        FREQUENCY_SAMPLING = 6e6
        FREQUENCY_CENTER = 94.5e6

        clength = 12000000
        us = PlutoSource(FREQUENCY_SAMPLING, FREQUENCY_CENTER, None, clength)
        print('Got source')
        times = []
        with trange(20) as t:
            for i in t:
                start_time = time.time()
                while(not us.samples_available()):
                    pass
                end_time = time.time()
                times.append(end_time-start_time)
                chunk = us.get_chunk()  
                print(end_time-start_time)
                t.set_postfix(time=(end_time-start_time))
        del us
        self.assertTrue(np.all(np.array(times[1:]) < clength/FREQUENCY_SAMPLING))


if __name__ == '__main__':
    unittest.main()