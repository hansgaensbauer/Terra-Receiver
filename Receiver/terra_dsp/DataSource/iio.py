from terra_dsp.DataSource import DataSource
from multiprocessing import Process, Queue, shared_memory, Event
import numpy as np
import time
import adi
import iio

class PlutoSource(DataSource):
    """Datasource for PlutoSDR (IIO) devices.
    """    
    def __init__(self, fs, fc, chunk_length=20000000, **kwargs):

        self.buffer_length = 2400000
        if(chunk_length % self.buffer_length != 0):
            raise ValueError(f'buffer size ({self.buffer_length}) must evenly divide chunk_length ({chunk_length})')
        self.running = False

        self.max_queue_length = 10
        self.index_queue = Queue(maxsize=self.max_queue_length)
        self.last_write_index = Queue(maxsize=self.max_queue_length)
        self.last_read_index = None

        chunk_bytes = chunk_length * np.dtype(np.complex64).itemsize

        self.shm_blocks = [
            shared_memory.SharedMemory(create=True, size=chunk_bytes)
            for _ in range(self.max_queue_length)
        ]
        self.arrays = [
            np.ndarray(chunk_length, dtype=np.complex64, buffer=shm.buf)
            for shm in self.shm_blocks
        ]

        self.shm_names = [shm.name for shm in self.shm_blocks]

        self.kwargs = kwargs
        self.fc = fc
        self.index = 0
        self.last_read_time = time.time()
        self.rx_process = None
        self.stop_flag = Event()
        self.running = False

        DataSource.__init__(self, fs, chunk_length)
        self.rx_process = Process(target=self._rx_process, 
                            args=(self.stop_flag, self.shm_names,self.kwargs), daemon=True)
        self.rx_process.start()
        self.start()

    def stop(self):
        self.stop_flag.clear()
        self.running = False

    def start(self):
        self.stop_flag.set()
        self.running = True

    def _rx_process(self, stop_flag, shm_names, kwargs):
        if('uri' in kwargs.keys()):
            uri = kwargs['uri']
        else:
            uri = get_uri()
        sdr = adi.Pluto(uri=uri)
        sdr.rx_rf_bandwidth = int(self.fs)
        sdr.sample_rate = int(self.fs)
        sdr.rx_lo = int(self.fc)
        sdr.rx_enabled_channels = [0]
        sdr.gain_control_mode_chan0 = "manual"
        sdr.rx_hardwaregain_chan0 = kwargs["gain"]
        sdr.rx_buffer_size = self.buffer_length

        shm_blocks = [shared_memory.SharedMemory(name=name) for name in shm_names]
        arrays = [
            np.ndarray(self.chunk_length, dtype=np.complex64, buffer=shm.buf)
            for shm in shm_blocks
        ]

        num_samples = 0
        shared_memory_index = 0
        while(1):
            while(stop_flag.is_set()):
                for i in range(self.chunk_length//self.buffer_length):
                    if(not stop_flag.is_set()):
                        break
                    arrays[shared_memory_index][i*self.buffer_length:(i+1)*self.buffer_length] = sdr.rx()

                num_samples += self.chunk_length
                if(self.index_queue.full()):
                    self.last_write_index.get()
                    self.index_queue.get()
                # print('adding sample')
                self.last_write_index.put(shared_memory_index)
                self.index_queue.put(num_samples)

                shared_memory_index = (shared_memory_index + 1) % self.max_queue_length
            num_samples = 0
            shared_memory_index = 0
            stop_flag.wait()
        
    def get_chunk(self):
        if(not self.samples_available):
            return None
        else:
            self.index = self.index_queue.get()
            self.last_read_index = self.last_write_index.get()
            return self.arrays[self.last_read_index]
    
    def samples_available(self):
        return not self.index_queue.empty()
    
    def flush(self):
        starting_index = self.index
        while(not self.index_queue.empty()):
            self.last_write_index.get()
            self.index = self.index_queue.get()
            # print(f'\tIndex: {self.index}')
        print(f'Removed {self.index - starting_index} samples')
        return round((self.index - starting_index)/self.chunk_length)
    
    def __del__(self):
        [mem.close() for mem in self.shm_blocks]
        [mem.unlink() for mem in self.shm_blocks]
        self.rx_process.terminate()

def get_uri():
    ctx = iio.scan_contexts()
    for uri, description in ctx.items():
        if "PlutoSDR" in description or "ADALM-PLUTO" in description:
            return uri
    
    return None
