from terra_client.LocationPipeline import LocationPipeline
import terra_client.NetworkClient
import terra_dsp.DataSource
import argparse
import pygeohash as pgh
import time
import os
import json
from dotenv import load_dotenv

if __name__ == "__main__":
    
    load_dotenv()

    parser = argparse.ArgumentParser(description='Run Terra Client')
    parser.add_argument('--source_file', action='store', help='Datasource config file', default=os.getenv("DATASOURCE_FILE"))
    parser.add_argument('--loc', action='store', type=str, help='Client location geohash (for use with simulated data)', default=os.getenv("CLIENT_GEOHASH"))
    parser.add_argument('--use_local_features', action='store_true', help='Get features from a file, not a web server')
    parser.add_argument('--url', action='store', help='Server URL', default=os.getenv("SERVER_URL"))    
    parser.add_argument('--features_dir', action='store', help='local feature directory', default=os.getenv("LOCAL_FEATURE_DIR"))
    parser.add_argument('-f', '--stations_file', action='store', help='Stations config file')

    args = parser.parse_args()

    # # Clean logs folder
    # dir_path = r"Logs"
    # for filename in os.listdir(dir_path):
    #     file_path = os.path.join(dir_path, filename)
    #     if os.path.isfile(file_path):
    #         os.remove(file_path)  

    with open(args.source_file, 'r') as json_file:
        source_json = json.load(json_file)

    if("start_time" in source_json.keys()):
        start_time = source_json["start_time"]
        print(f'Overriding Start time to {start_time}')
    else:
        start_time = None

    if(args.use_local_features):
        print(f'Using local features saved in {args.features_dir}')
        print(f'Using stations saved in {args.stations_file}')
        network_client = terra_client.NetworkClient.FileClient(args.features_dir, args.stations_file)
    else:
        print(f'Using API Client')
        if(args.url == ''):
            raise ValueError("Server URL environment variable (SERVER_URL) is not set.")
        
        network_client = terra_client.NetworkClient.APIClient(args.url)

    if(source_json["driver"] == 'random'):
        stations = network_client.get_served_stations(args.loc,source_json["start_time"])
        print(stations)
        lat, lon = pgh.decode(geohash=args.loc)
        client_location = [lat, lon]
        datasource = terra_dsp.DataSource.RandomSource(source_json["fs"], source_json["fc"], source_json["chunk_length"],
                                                    stations=stations,
                                                    client_location=client_location, **source_json["source_kwargs"])    
        
    elif(source_json["driver"] == 'file'):
        if("data_file" not in source_json):
            raise ValueError("Data file is required for recorded data.")
        from terra_dsp.DataSource import FileSource
        datasource = FileSource(args.data_file, source_json["fs"], source_json["fc"], source_json["chunk_length"], **source_json["source_kwargs"])
    elif(source_json["driver"] == 'usrp'):
        from terra_dsp.DataSource.uhd import USRPSource
        datasource = USRPSource(source_json["fs"], source_json["fc"], source_json["chunk_length"], **source_json["source_kwargs"])
    elif(source_json["driver"] == 'pluto'):
        from terra_dsp.DataSource.iio import PlutoSource
        datasource = PlutoSource(source_json["fs"], source_json["fc"], source_json["chunk_length"], **source_json["source_kwargs"])
    elif(source_json["driver"] == 'soapy'):
        from terra_dsp.DataSource.soapy import SoapySource
        datasource = SoapySource(source_json["fs"], source_json["fc"], source_json["chunk_length"], **source_json["source_kwargs"])
    else:
        driver = source_json["driver"]
        raise ValueError(f"Unsupported driver {driver}.")
    
    if("start_time" in source_json.keys()):
        start_time = source_json["start_time"]
        print(f'Overriding Start time to {start_time}')
    else:
        start_time = None

    print(args.loc)
    solver = LocationPipeline(datasource, network_client, args.loc, start_time)

    while(True):
        solution = solver.solve()
        if(solution is not None):
            print([float(nfloat) for nfloat in solution["location"]])
            time.sleep(6)
