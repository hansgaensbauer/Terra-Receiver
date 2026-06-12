import numpy as np
import time
from terra_dsp.Station import Station
from terra_dsp.visualization_tools import plot_prop, _latlon_to_meters

class DataSource:
    """Generic DataSource class. This is used for abstracting different radios, testing inputs, etc.
    """    
    def __init__(self, fs, chunk_length):
        self.fs = fs
        self.chunk_length = chunk_length

    def samples_available():
        """Check if there are samples available from this datasource

        Returns:
            bool: True if there are samples available.
        """        
        return False

    def get_chunk(self):
        """Fetch a chunk of samples

        Returns:
            np.array: Samples
        """        
        return None
    
    def stop():
        """Stop data collection.
        """        
        pass

    def start():
        """Start data collection.
        """        
        pass
     
class FileSource(DataSource):
    """DataSource that draws from a raw (IQ) file, like those from GQRX.
    """    
    def __init__(self, filename, fs, fc, chunk_length=20000000):
        """Constructor for FileSource 

        Args:
            filename (str): Sample file name.
            fs (float): Sampling rate (Hz).
            fc (float): Center frequency (Hz).
            chunk_length (int, optional): Number of samples per  chunk. Defaults to 20000000.
        """        
        self.data = np.fromfile(filename, np.complex64)[28*4000000:]
        self.fc = fc
        self.index = 0
        self.last_read_time = time.time()
        DataSource.__init__(self, fs, chunk_length)
        
    def get_chunk(self):
        """Fetch a chunk of samples

        Returns:
            np.array: Samples
        """        
        if(not self.samples_available()):
            return None
        self.index += self.chunk_length
        self.last_read_time = time.time()
        if(self.index < len(self.data)):
            data_chunk = self.data[self.index - self.chunk_length:self.index]
        else:
            data_chunk = np.concatenate([self.data[self.index - self.chunk_length:], self.data[:self.index % len(self.data)]])
            self.index = self.index % len(self.data)
        return data_chunk
    
    def samples_available(self):
        """Check if there are samples available from this datasource.

        Returns:
            bool: True if there are samples available.
        """      
        return time.time() > (self.chunk_length / self.fs) + self.last_read_time
    
    def flush(self):
        return 0

