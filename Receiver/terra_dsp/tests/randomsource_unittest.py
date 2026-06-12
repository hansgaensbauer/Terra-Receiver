import unittest
import numpy as np
from terra_dsp.channelizer import freq_shift_filter_cpu
from terra_dsp.Station import Station
from terra_dsp.DataSource import RandomSource
import geopy.distance
import scipy.signal as sg
from terra_dsp.score_functions import max_mean_ratio_cpu, max_mean_ratio_gpu
from tqdm import tqdm
import time

class TestRandomSource(unittest.TestCase):

    def test_singleband_fullrate_delay(self):
        fs = 6e6
        fc = 94.5e6
        ref_location = [42.361515, -71.091975]
        stations = [
            Station(94.5e6, 400e3, [42.307583, -71.223667], 'WJMN'),
            Station(95.3e6, 400e3, [42.352333, -71.056444], 'WHRB'),
            Station(92.9e6, 400e3, [42.347333, -71.082556], 'WBOS'),
            Station(92.5e6, 400e3, [42.387028, -71.076111], 'WXRV'),
            Station(96.9e6, 400e3, [42.347, -71.083], 'WBQT'),
            Station(96.5e6, 400e3, [42.35225, -71.056278], 'W243DC'),
        ]

        c_air = 299702458
        for station in tqdm(stations):
            rs = RandomSource(37, fs, fc, 6000000, stations=[station], ref_location=ref_location)
            rs_zd = RandomSource(37, fs, fc, 6000000, stations=[station], ref_location=ref_location, zerodelay=True)
            while(not rs_zd.samples_available()):
                pass
            while(not rs.samples_available()):
                pass
            rs_chunk = rs.get_chunk()
            zero_delay_chunk = rs_zd.get_chunk()

            # zero_delay_chunk = get_zerodelay_chunk(6000000, fc, fs, [station])
            

            refrange = geopy.distance.geodesic(station.location, ref_location).m

            corr = sg.correlate(zero_delay_chunk, rs_chunk)
            
            argmax = np.argmax(np.abs(corr))
            delay = (argmax - (len(corr)//2))/fs

            self.assertTrue(np.abs(delay*c_air + refrange) < 50)
            del(rs)
            del(rs_zd)

    def test_singleband_baseband_delay(self):
        fs = 6e6
        fc = 94.5e6
        ref_location = [42.361515, -71.091975]
        stations = [
            Station(94.5e6, 400e3, [42.307583, -71.223667], 'WJMN'),
            Station(95.3e6, 400e3, [42.352333, -71.056444], 'WHRB'),
            Station(92.9e6, 400e3, [42.347333, -71.082556], 'WBOS'),
            Station(92.5e6, 400e3, [42.387028, -71.076111], 'WXRV'),
            Station(96.9e6, 400e3, [42.347, -71.083], 'WBQT'),
            Station(96.5e6, 400e3, [42.35225, -71.056278], 'W243DC'),
        ]

        c_air = 299702458
        for station in tqdm(stations):
            rs = RandomSource(37, fs, fc, 6000000, stations=[station], ref_location=ref_location)
            rs_zd = RandomSource(37, fs, fc, 6000000, stations=[station], ref_location=ref_location, zerodelay=True)
            while(not rs.samples_available()):
                pass
            rs_chunk = rs.get_chunk()
            
            while(not rs_zd.samples_available()):
                pass
            zero_delay_chunk = rs_zd.get_chunk()

            refrange = geopy.distance.geodesic(station.location, ref_location).m
            chunk_bb = freq_shift_filter_cpu(rs_chunk, station.frequency - fc, fs, 0)
            chunk_zero_bb = freq_shift_filter_cpu(zero_delay_chunk, station.frequency - fc, fs, 0)
            corr_bb = sg.correlate(chunk_zero_bb, chunk_bb)
            
            argmax = np.argmax(np.abs(corr_bb))
            delay = (argmax - (len(corr_bb)//2))/400_000

            self.assertTrue(np.abs(delay*c_air + refrange) < 700)
            del(rs)
            del(rs_zd)
        

    def test_multiband_delays(self):
                
        fs = 6e6
        fc = 94.5e6
        ref_location = [42.361515, -71.091975]
        stations = [
            Station(94.5e6, 500e3, [42.307583, -71.223667], 'WJMN'),
            Station(95.3e6, 500e3, [42.352333, -71.056444], 'WHRB'),
            Station(92.9e6, 500e3, [42.347333, -71.082556], 'WBOS'),
            Station(92.5e6, 500e3, [42.387028, -71.076111], 'WXRV'),
            Station(96.9e6, 500e3, [42.347, -71.083], 'WBQT'),
            Station(96.5e6, 500e3, [42.35225, -71.056278], 'W243DC'),
        ]

        rs = RandomSource(37, fs, fc, 6000000, stations=stations, ref_location=ref_location)
        rs_zd = RandomSource(37, fs, fc, 6000000, stations=stations, ref_location=ref_location, zerodelay=True)
        while(not rs_zd.samples_available()):
            pass
        while(not rs.samples_available()):
            pass
        rs_chunk = rs.get_chunk()
        zero_delay_chunk = rs_zd.get_chunk()

        refrange = []
        for i in range(len(stations)):
            refrange.append(geopy.distance.geodesic(stations[i].location, ref_location).m)

        delays = []
        for i in tqdm(range(len(stations))):
            chunk_bb = freq_shift_filter_cpu(rs_chunk, stations[i].frequency - fc, fs, 0)
            chunk_zero_bb = freq_shift_filter_cpu(zero_delay_chunk, stations[i].frequency - fc, fs, 0)
            corr_bb = sg.correlate(chunk_zero_bb, chunk_bb)
            
            argmax = np.argmax(np.abs(corr_bb))
            delays.append((argmax - (len(corr_bb)//2))/400_000)
            
        c_air = 299702458
        delays = np.array(delays)
        self.assertTrue(np.all(np.abs(delays*c_air + np.array(refrange)) < 600))


    def test_flush(self):
                
        fs = 6e6
        fc = 94.5e6
        ref_location = [42.361515, -71.091975]
        stations = [
            Station(94.5e6, 500e3, [42.307583, -71.223667], 'WJMN'),
            Station(95.3e6, 500e3, [42.352333, -71.056444], 'WHRB')
        ]

        rs = RandomSource(37, fs, fc, 6000000, stations=stations, ref_location=ref_location)
        rs_slow = RandomSource(37, fs, fc, 6000000, stations=stations, ref_location=ref_location)
        while(not rs_slow.samples_available()):
            pass
        while(not rs.samples_available()):
            pass

        rs_chunk = rs.get_chunk()
        slow_chunk = rs_slow.get_chunk()

        self.assertTrue(np.allclose(rs_chunk, slow_chunk))

        #get a bunch of chunks from the rs source
        half_chunk_delay = 0.5

        # Test less than queue length
        print("Advancing one RandomSource")
        for i in tqdm(range(3)):
            while(not rs.samples_available()):
                pass
            rs_chunk = rs.get_chunk()

        time.sleep(half_chunk_delay)

        print("Flushing slow data source")
        rs_slow.flush()

        while(not rs_slow.samples_available()):
            pass
        while(not rs.samples_available()):
            pass

        rs_chunk = rs.get_chunk()
        slow_chunk = rs_slow.get_chunk()

        self.assertTrue(np.allclose(rs_chunk, slow_chunk))

        #Test more than queue length
        print("Advancing one RandomSource")
        for i in tqdm(range(15)):
            while(not rs.samples_available()):
                pass
            rs_chunk = rs.get_chunk()
        
        time.sleep(half_chunk_delay)

        print("Flushing slow data source")
        rs_slow.flush()

        while(not rs_slow.samples_available()):
            pass
        while(not rs.samples_available()):
            pass

        rs_chunk = rs.get_chunk()
        slow_chunk = rs_slow.get_chunk()

        self.assertTrue(np.allclose(rs_chunk, slow_chunk))

        del rs
        del rs_slow

if __name__ == '__main__':
    unittest.main()