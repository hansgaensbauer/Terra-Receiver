import time
from multiprocessing import Process, Queue
import numpy as np
import geopy.distance
from terra_dsp.DataSource import DataSource

class RandomSource(DataSource):
    """A random data that accurately simulates propagation.
    """    
    c_air_ns = 0.299702458
    def __init__(self, fs, fc, chunk_length=20000000, seed=37, stations=None, ref_location=None, zerodelay=False):
        """RandomSource Constructor

        Args:
            fs (float): sample rate (Hz).
            fc (float): center frequency (Hz).
            chunk_length (int, optional): Number of samples per chunk. Defaults to 20000000.
            seed (int, optional): Random seed. Defaults to 37.
            stations (list[Station], optional): list of Station objects to use for simulation. Defaults to None.
            ref_location (list[Latitude, Longitude], optional): Location of the reference receiver. Defaults to None.
            zerodelay (bool, optional): Set to true to skip simulation and use zero propagation delay for all stations. Defaults to False.
        """        

        print('Creating Randomsource')
        self.rng = np.random.default_rng(seed=seed)
        self.start_time = time.time()
        self.fc = fc
        self.stations = stations
        self.ref_location = ref_location
        self.zerodelay = zerodelay
        self.which_buffer = 0
        self.index = 0
        self.worker_running = True
        self.max_queue_length = 10

        self.sample_queue = Queue(maxsize=self.max_queue_length)
        self.index_queue = Queue(maxsize=self.max_queue_length)

        #precompute linear filters 
        self.phase_shifts = []
        if(not self.zerodelay):
            for station in self.stations:
                f_bb = station.frequency - self.fc
                f_bb_center = int((fs/2 + f_bb)/(fs)*chunk_length)
                bandwidth_bins = int(station.bandwidth/fs*chunk_length)
                refrange = geopy.distance.geodesic(station.location, self.ref_location).m
                delay_ns = refrange/self.c_air_ns
                freqs = np.fft.fftfreq(chunk_length, d=1/fs)
                band_freqs = np.fft.fftshift(freqs)[f_bb_center-bandwidth_bins//2:f_bb_center+bandwidth_bins//2]
                self.phase_shifts.append(np.exp(-1j*2*np.pi*band_freqs*delay_ns/1e9))

        self.rx_process = Process(target=self._create_next_chunk, daemon=True)

        DataSource.__init__(self, fs, chunk_length)

        #create the first set of samples
        self.rx_process.start()

    def get_chunk(self):
        """Fetch a chunk of samples

        Returns:
            np.array: Samples
        """      
        if(not self.samples_available):
            return None
        else:
            self.index = self.index_queue.get()
            return self.sample_queue.get()

    def _create_next_chunk(self):
        num_samples = 0
        while(self.worker_running):
            sg_freq_domain = np.zeros(self.chunk_length, dtype=np.complex128)
            samples = sg_freq_domain
            if(self.stations is not None):
                for i in range(len(self.stations)):
                    station = self.stations[i]
                    f_bb = station.frequency - self.fc
                    f_bb_center = int((self.fs/2 + f_bb)/(self.fs)*self.chunk_length)
                    bandwidth_bins = int(station.bandwidth/self.fs*self.chunk_length)

                    band_limited_random = (self.rng.random(bandwidth_bins) - 0.5) + 1j*(self.rng.random(bandwidth_bins) - 0.5)

                    if(not self.zerodelay):
                        phase_shift = self.phase_shifts[i]
                    else:
                        phase_shift = 1
                    sg_freq_domain[f_bb_center-bandwidth_bins//2:f_bb_center+bandwidth_bins//2] = band_limited_random * phase_shift

                sg_time_domain = np.fft.ifft(np.fft.fftshift(sg_freq_domain))
                
                samples = sg_time_domain
            else:
                samples = self.rng.normal(0,0.1,self.chunk_length)
            num_samples += self.chunk_length
            if(self.sample_queue.full() and 
               (time.time() - self.start_time) > (num_samples + self.max_queue_length * self.chunk_length)/self.fs):
                self.sample_queue.get()
                self.index_queue.get()
            self.sample_queue.put(samples.astype(np.complex64))
            self.index_queue.put(num_samples)
    
    def samples_available(self):
        """Check if there are samples available from this datasource.

        Returns:
            bool: True if there are samples available.
        """    
        if(time.time() < (self.chunk_length + self.index) / self.fs + self.start_time or self.sample_queue.empty()):
            return False
        else:
            return True
        
    def flush(self):
        """Clear all chunks in the buffer, so that the next chunk matches the current server time.

        Returns:
            int: Number of dropped chunks
        """        
        time_running = time.time() - self.start_time
        target_index = int(time_running * self.fs)
        # print(f'target_index: {target_index}')
        # print(f'Starting Index: {self.index}')
        if(self.index > target_index - self.chunk_length):
            return 0
        else:
            starting_index = self.index
            while(self.index < target_index - self.chunk_length):
                self.sample_queue.get()
                self.index = self.index_queue.get()
                # print(f'\tIndex: {self.index}')
            print(f'Removed {self.index - starting_index} samples')
            return round((self.index - starting_index)/self.chunk_length)
        
    def __del__(self):
        self.worker_running = False
        self.rx_process.terminate()
