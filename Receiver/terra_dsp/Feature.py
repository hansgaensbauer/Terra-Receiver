from dataclasses import dataclass
import numpy as np

@dataclass
class Feature:
    """A dataclass representing signal features. 
    """    
    timestamp: int
    StationID: int
    FeatureData: np.ndarray
    index: int = -1

    def __str__(self):
        return f'Feature: {self.StationID}@{self.timestamp}'
    
    def __repr__(self):
        return f'Feature: {self.StationID}@{self.timestamp}'