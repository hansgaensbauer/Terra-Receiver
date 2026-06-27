from terra_dsp.Station import Station
from terra_dsp.Feature import Feature
import json
import os
import pickle
import requests
import msgpack
import pygeohash as pgh
import numpy as np

class NetworkClient:
    """Prototype class for receiver network connections
    """    
    def __init__(self):
        pass

    def get_features(self):
        pass

    def get_served_stations(self):
        pass


class LocalClient(NetworkClient):
    """A NetworkClient that uses an internet connection to fetch features from a Local 
    Terra backend..

    :param url: API URL
    :type url: str
    """    
    def __init__(self, url):
        """Class constructor
        """        
        super().__init__()
        self.url = url

    def get_features(self, region, time):
        """Retrieve features from the backend.

        :param region: 3 letter geohash of client receiver location. 
        :type region: str
        :param time: Receive window start time in nanoseconds from the epoch.
        :type time: int

        :return: Dictionary mapping StationIDs to a list of Feature objects for that station.
        :rtype: dict
        """        
        url = self.url + f'?region={region}&time={time}'
        response = requests.get(url)
        if response.status_code == 200:
            resp = pickle.loads(response.content)
            features = {}
            for resp_feature in resp:
                feature = Feature(resp_feature[1], resp_feature[0], resp_feature[2])
                if feature.StationID in features.keys():
                    features[feature.StationID].append(feature)
                else:
                    features[feature.StationID] = [feature]
            return features
        else:
            print(f'Error: {response.status_code}') 

    def get_served_stations(self, region, start_time):
        """Find stations with recent features in the region.

        :param region: geohash for the region.
        :type region: str
        :param start_time: Receive window start time in nanoseconds from the epoch.
        :type start_time: int

        :return: list of nearby stations with available features.
        :rtype: list[Station]
        """        
        url = self.url + f'stations/?region={region}&time={start_time}'
        response = requests.get(url)
        if response.status_code == 200:
            resp = response.json()
            stations = []
            for station_resp in resp:
                stations.append(Station(station_resp[2]*1000000, 400_000, [float(station_resp[3]), float(station_resp[4])], station_resp[1], station_resp[0]))
            return stations
        else:
            print(f'Error: {response.status_code}') 

class APIClient(NetworkClient):
    """A NetworkClient that uses an internet connection to fetch features from the 
    Terra backend using a the Terra API.

    :param url: API URL
    :type url: str
    """    
    def __init__(self, url):
        """Class constructor
        """        
        super().__init__()
        self.url = url

    def get_token(self):
        COGNITO_DOMAIN = os.environ['COGNITO_DOMAIN']
        CLIENT_ID = os.environ['FEATURE_CLIENT_ID']
        CLIENT_SECRET = os.environ['FEATURE_CLIENT_SECRET']
        SCOPE = 'default-m2m-resource-server-coqa-/read'
        response = requests.post(
            f'{COGNITO_DOMAIN}/oauth2/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'scope': SCOPE,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        response.raise_for_status()
        return response.json()['access_token']

    def get_features(self, stations, time):
        """Retrieve features from the backend.

        :param stations: List of Station objects to request features for.
        :type region: List[Station]
        :param time: Receive window start time in nanoseconds from the epoch.
        :type time: int

        :return: Dictionary mapping StationIDs to a list of Feature objects for that station.
        :rtype: dict
        """        
        token = self.get_token()
        station_ids = [station.StationID for station in stations]

        response = requests.get(
            self.url + '/features',
            params={
                'station_ids': ','.join(station_ids),
                'time_from': str(time - 3_000_000_000),
                'time_to': str(time + 4_000_000_000),
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        response.raise_for_status()
        msg = msgpack.unpackb(response.content, raw=False)
        features = {}
        for stationid in msg.keys():
            for featuredict in msg[stationid]:
                feature = Feature(featuredict['timestamp'],
                                   featuredict['station_id'],
                                     np.array(featuredict['real'], dtype=np.complex64) + 
                                     1j*np.array(featuredict['imag'], dtype=np.complex64))
                if feature.StationID in features.keys():
                    features[feature.StationID].append(feature)
                else:
                    features[feature.StationID] = [feature]
        return features

    def get_served_stations(self, region, start_time):
        """Find stations with recent features in the region.

        :param region: geohash for the region.
        :type region: str
        :param start_time: Receive window start time in nanoseconds from the epoch. Not used.
        :type start_time: int

        :return: list of nearby stations with available features.
        :rtype: list[Station]
        """        
        lat, lon = pgh.decode(geohash=region)
        print(self.url + '/stations')
        response = requests.get(
            self.url + '/stations',
            params={
                'lat':str(lat),
                'lon':str(lon)
            }
            )
        response.raise_for_status()
        if response.status_code == 200:
            resp = response.json()
            stations = []
            for station_resp in resp['stations']:
                stations.append(Station(int(station_resp['frequency']),
                                         int(station_resp['bandwidth']), 
                                         [float(station_resp['lat']), float(station_resp['lon'])], 
                                         station_resp['callsign'], 
                                         station_resp['station_id']))
            return stations
        else:
            print(f'Error: {response.status_code}') 

class FileClient(NetworkClient):
    """An offline NetworkClient that serves features from a file for testing.

    :param feature_dir: Directory containing feature files.
    :type feature_dir: str
    :param stations_file: File path for station definition json file.
    :type stations_file: str
    """    

    def __init__(self, feature_dir, stations_file):
        """Class constructor
        """        
        self.feature_dir = feature_dir
        self.stations_file = stations_file

        with open(stations_file, 'r') as json_file:
            stations_json = json.load(json_file)

        # Convert to station objects
        self.stations = []
        for json_station in stations_json:
            self.stations.append(Station(json_station["frequency"], 
                                    json_station["bandwidth"], 
                                    json_station["coords"], 
                                    json_station["callsign"],
                                    json_station["StationID"]))
        
        super().__init__()

    def get_served_stations(self, region, time):
        """Find stations with recent features in the region.

        :param region: geohash for the region. Not used.
        :type region: str
        :param start_time: Receive window start time in nanoseconds from the epoch. Not used.
        :type start_time: int

        :return: list of nearby stations with available features.
        :rtype: list[Station]
        """     
        return self.stations
    
    def get_features(self, stations, time):
        """Retrieve features from the file.

        :param stations: 3 letter geohash of client receiver location. Not used.
        :type region: str
        :param time: Receive window start time in nanoseconds from the epoch. Not used.
        :type time: int

        :return: Dictionary mapping StationIDs to a list of Feature objects for that station.
        :rtype: dict
        """      
        features = {}
        with open(self.feature_dir + '/features2400000.pickle', 'rb') as file:
            features_list = pickle.load(file)

        for ft in features_list:
            if(ft.StationID in features.keys()):
                features[ft.StationID].append(ft)
            else:
                features[ft.StationID] = [ft]
        
        # print(features[1])
            
        # #crappy hack: update all the timestamps
        # min_timestamp = features[sorted(features.keys())[4]][0].timestamp
        # offset = time - min_timestamp

        # print('\tSimulated Features')
        # print(f'\t\tMin Timestamp: {min_timestamp}')
        # print(f'\t\toffset: {offset}')

        # for station_id in features.keys():
        #     for feature in features[station_id]:
        #         feature.timestamp = feature.timestamp + offset

        return features