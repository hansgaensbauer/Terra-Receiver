from dataclasses import dataclass

@dataclass
class Station:
    """A dataclass representing stations. 
    """    

    frequency: float
    bandwidth: float
    location: list
    name: str
    StationID: int = 0

    def __str__(self):
        station_string = f"""{self.name}:
            \tFrequency: {self.frequency}
            \tBandwidth: {self.bandwidth}
            \tLocation: {self.location}
            \tStationID: {self.StationID}"""
        return station_string
    
    def __repr__(self):
        return self.name