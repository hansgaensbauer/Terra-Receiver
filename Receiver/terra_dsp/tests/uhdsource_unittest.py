import unittest
from terra_dsp.DataSource.uhd import USRPSource
import scipy.signal as sg
from tqdm import tqdm
import time

class TestUSRP(unittest.TestCase):

    def test_getdata(self):
                
        fs = 6e6
        fc = 94.5e6

        us = USRPSource(fs, fc, 6000000)
        print('Got source')
        while(not us.samples_available()):
            pass

        chunk = us.get_chunk()        
        print("Got chunk")
        del us
        self.assertTrue(len(chunk) == 6000000)


if __name__ == '__main__':
    unittest.main()