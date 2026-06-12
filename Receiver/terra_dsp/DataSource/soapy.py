from terra_dsp.DataSource import DataSource
from multiprocessing import Process, Queue, shared_memory, Event
import numpy as np
import time
import SoapySDR
from SoapySDR import *

class SoapySource(DataSource):
    """Datasource for SoapySDR devices.
    """    
    def __init__(self, fs, fc, chunk_length=20000000, **kwargs):

        self.buffer_length = 2400000
        self.max_queue_length = 10

        if(chunk_length % self.buffer_length != 0):
            raise ValueError(f'buffer size ({self.buffer_length}) must evenly divide chunk_length ({chunk_length})')
        self.running = False
        
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

        self.fc = fc
        self.index = 0
        self.kwargs = kwargs
        self.last_read_time = time.time()
        self.running = False
        self.stop_flag = Event()
        self.rx_process = None
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
        
        shm_blocks = [shared_memory.SharedMemory(name=name) for name in shm_names]
        arrays = [
            np.ndarray(self.chunk_length, dtype=np.complex64, buffer=shm.buf)
            for shm in shm_blocks
        ]

        sdr = SoapySDR.Device(kwargs["device_string"])
        sdr.setSampleRate(SOAPY_SDR_RX, 0, self.fs)
        sdr.setFrequency(SOAPY_SDR_RX, 0, self.fc)

        if("antenna" in kwargs.keys()):
            sdr.setAntenna(SOAPY_SDR_RX, 0, kwargs["antenna"])

        if("gains" in kwargs.keys()):
            for amp, gain in kwargs["gains"].items():
                sdr.setGain(SOAPY_SDR_RX, 0, amp, gain)

        rxStream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
        sdr.activateStream(rxStream)

        num_samples = 0
        shared_memory_index = 0

        buff = np.array([0]*self.buffer_length, np.complex64)
        while(1):
            while(stop_flag.is_set()):
                for i in range(self.chunk_length//self.buffer_length):
                    if(not stop_flag.is_set()):
                        break
                    sr = sdr.readStream(rxStream, [buff], self.buffer_length)
                    arrays[shared_memory_index][i*self.buffer_length:(i+1)*self.buffer_length] = buff

                num_samples += self.chunk_length
                if(self.index_queue.full()):
                    self.last_write_index.get()
                    self.index_queue.get()

                self.last_write_index.put(shared_memory_index)
                self.index_queue.put(num_samples)

                shared_memory_index = (shared_memory_index + 1) % self.max_queue_length

            sdr.deactivateStream(rxStream) #stop streaming
            sdr.closeStream(rxStream)
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
