
from terra_client.WebSocketSender import WebSocketSender
from terra_dsp.channelizer import freq_shift_filter_cpu, cpu_arbfreq_channelizer, compute_pfb_channelizer, get_pfb_channelizer
import terra_dsp.DataSource
from terra_dsp.visualization_tools import plot_prop, plot_signal_timing
import terra_client.NetworkClient

import requests
import numpy as np
import scipy.signal as sg
import scipy.optimize as opt
import time
import matplotlib.pyplot as plt
import fractions

class LocationPipeline:
    """This class contains everything required to produce a location estimate on a client mobile receiver.

    :param data_source: Input signal source for this receiver
    :type data_source: terra_dsp.DataSource
    :param network_client: Network connection for this receiver
    :type network_client: terra_client.NetworkClient
    :param region: The rough geographic region of the receiver. Used to determine which reference features to serve. This should be a three character geohash.
    :type region: str
    :param override_time: For testing. This overrides the receiver start time so that recorded data can be used. Defaults to None.
    :type override_time: int, optional
    :param channel_width: Channel bandwidth in Hz. Defaults to 400_000.
    :type channel_width: int, optional
    """    
    C = 299705543
    FEATURE_LEN = 400
    def __init__(self, 
                 data_source, 
                 network_client, 
                 region,
                 override_time = None,
                 channel_width = 400_000
                 ):
        """LocationPipeline constructor
        """        

        self.region = region
        self.best_station_index = None
        self.data_source = data_source
        self.decimation = round(self.data_source.fs/channel_width)
        self.fs_demod = channel_width
        self.ds_fractional_fs = fractions.Fraction(numerator=int(self.data_source.fs), denominator=1_000_000_000)
        self.fractional_fs_demod = fractions.Fraction(numerator=self.fs_demod, denominator=1_000_000_000)
        self.network_client = network_client
        self.rf_data = None
        self.baseband_data = None
        self.stations = None
        if(override_time is None):
            self.start_time = time.time_ns()
        else:
            self.start_time = override_time
        self.clock_offset = 0
        self.lo_correction = None
        self.valid_features = None
        self.lo = None
        self.resample_factor = None
        self.override_time = override_time
        self.run_start_time = time.time_ns()
        
    def solve(self):
        """Receive RF data, request signals from the server, and attempt to produce a location

        :raises ValueError: Raises a ValueError if the pfb channelizer is used and an invalid channel is requested.

        :return: A dictionary containing the location estimate, the pseudoranges, and the time offset.
        :rtype: dict
        """        
        #Receive 1 chunk of RF_data
        #TODO Hans: how to make sure that rx_start_time corresponds to the actual first sample
        print('Getting Data...')
        # dropped_chunks = self.data_source.flush()
        if(not self.data_source.running):
            self.data_source.start()
            while(not self.data_source.samples_available()):
                time.sleep(0.1) 
        dropped_chunks = self.data_source.flush()

        print(f'DS wait start: {time.time()}')
        while(not self.data_source.samples_available()):
            time.sleep(0.1) 

        if(self.override_time is not None):
            print('Using override time')
            rx_start_time = self.override_time + time.time_ns() - self.run_start_time + self.clock_offset
        else:
            rx_start_time = time.time_ns() - round(self.data_source.chunk_length / self.ds_fractional_fs) + self.clock_offset

        self.rf_data = self.data_source.get_chunk()
        print(f'start: {rx_start_time/1e9}')

        # self.data_source.stop()
        print(f'\tLoaded {len(self.rf_data)} samples.')

        # Save raw data
        with open(f'Logs/{rx_start_time}.raw', 'wb') as f:
            self.rf_data.astype(np.complex64).tofile(f)


        print(rx_start_time)
        self.stations = self.network_client.get_served_stations(self.region, rx_start_time)
        print(f'\tStations: {self.stations}')

        print('Demodulating All Signals...\n')

        if(True):
            NTAPS = 60*16

            f_bb = np.array([station.frequency - self.data_source.fc for station in self.stations])
            channels = round(self.data_source.fs/self.fs_demod) 
            if(channels % 2):
                channel_freqs = np.roll(np.arange(-self.data_source.fs//2 + self.fs_demod//2, 
                                                self.data_source.fs//2, 
                                                self.fs_demod), channels//2)
            else:
                channel_freqs = np.roll(np.arange(-self.data_source.fs//2, 
                                                self.data_source.fs//2, 
                                                self.fs_demod), channels//2 - 1)

            channel_mask = []
            for i in range(len(f_bb)):
                channel_idx = np.where(channel_freqs == f_bb[i])[0]
                if(len(channel_idx)) != 1:
                    raise ValueError("Invalid channel")
                channel_mask.append(channel_idx[0])

            taps = compute_pfb_channelizer(self.data_source.chunk_length, NTAPS, channels)
            channelizer = get_pfb_channelizer(taps, channels, channel_mask)

            bb_freqs = [station.frequency - self.data_source.fc for station in self.stations]
            self.baseband_data = channelizer(self.rf_data, bb_freqs, self.data_source.fs, 0)

        else:
            self.baseband_data = cpu_arbfreq_channelizer(self.rf_data, bb_freqs, self.data_source.fs, 0, rate=self.decimation)

        time.sleep(10)
        #get features
        print('Retrieving features from the server...')
        features = self.network_client.get_features(self.region, rx_start_time)

        sig, ax = plt.subplots()
        plot_signal_timing(features,len(self.rf_data),4e6,rx_start_time, ax=ax, show=False)
        plt.savefig(f"Logs/featuretiming.png", dpi=300, bbox_inches='tight')
        plt.close('all')

        print(f'\tReceived {len(features)} feature arrays.')
        
        print('Getting Best Signal...')
        self.best_station_index = 1# self.get_best_station()

        best_station_id = self.stations[self.best_station_index].StationID
        print(f'\tBest station feature array has {len(features[best_station_id])} features.')

        #identify the strongest signal
        print(f'Best signal: {self.stations[self.best_station_index]}')

        if(True or self.resample_factor is None or self.lo_correction is None):

            best_station_demod = self.baseband_data[self.best_station_index]
            
            if(self.lo_correction is None):
                print('Calculating LO Correction...')
                self.lo_correction = 10000 #self.get_lo_correction(best_station_demod)
                print(f'\tLO Correction: {self.lo_correction} radians/s\n')
            
                t = np.arange(len(best_station_demod))/self.fs_demod
                self.lo = np.exp(-1j*self.lo_correction*t)
            if(True):
                print('Calculating Clock Offset...')
                signal_local_resamp = sg.resample(best_station_demod * self.lo, int(len(best_station_demod)/1))
                self.clock_offset = self.calculate_clock_offset(features[best_station_id], 
                                                                best_station_demod * self.lo, 
                                                                rx_start_time, 
                                                                self.fs_demod)     
                if(self.clock_offset is None):
                    self.clock_offset = 0
                    return None                   
                print(f'\tClock Offset: {self.clock_offset/1e9}\n')
                
            self.valid_features = self.get_valid_features(features, 
                                                    rx_start_time + self.clock_offset, 
                                                    len(best_station_demod))
            
            sig, ax = plt.subplots()
            plot_signal_timing(self.valid_features,len(self.rf_data),4e6, rx_start_time + self.clock_offset,ax=ax, show=False)
            plt.savefig(f"Logs/{best_station_id}_featuretiming_postcal.png", dpi=300, bbox_inches='tight')
            plt.close('all')

            if(self.resample_factor is None):
                print('Calculating Resample Rate...')
                best_station_demod_lo_corrected = best_station_demod * self.lo
                self.resample_factor = 0.999985 #self.calculate_sample_rate_offset(best_station_demod_lo_corrected, 
                                                                    # self.valid_features[best_station_id])
                
                print(f'\tResample Rate: {self.resample_factor}\n')
    
        #process each station, get pseudoranges
        print('Calculating Pseudoranges...')
        center  = [np.mean([station.location[0] for station in self.stations]),
                np.mean([station.location[1] for station in self.stations])]
        pseudoranges = []
        locations = []
        good_stations = []
        for idx, station in enumerate(self.stations):
            if(station.StationID == 1):
                station.location = [42.31028, -71.236668]
            #demodulate
            signal_local_bb = self.baseband_data[idx] * self.lo
            signal_local_resamp = sg.resample(signal_local_bb, int(len(signal_local_bb)/self.resample_factor))
            print(station.name)
            pseudorange = self.get_pseudorange(signal_local_resamp, self.valid_features[station.StationID],station.name)
            if(pseudorange is not None):
                good_stations.append(station)
                pseudoranges.append(pseudorange)
                locations.append(self._latlon_to_meters(center, station.location))
            else:
                print(f"Bad correlation. Dropping pseudorange for stationID {station.name}")
        
        print(f'\tPseudoranges: {pseudoranges}\n')

        #Solve for location
        print('Solving...')

        print(f'locations: {locations}')
        print(f'\tcenter: {center}')

        # set up equation
        def _residual(params, station_locations, pseudoranges):
            dt = params[0]
            x = params[1]
            y = params[2]
            residuals = np.zeros(len(station_locations))
            for i in range(len(station_locations)):
                distance = np.sqrt((station_locations[i][0] - params[1])**2 + (station_locations[i][1] - params[2])**2)
                residuals[i] = distance + dt * self.C - pseudoranges[i] * self.C
            return residuals

        x0 = [0,6e3,6e3]
        result = opt.least_squares(_residual, x0, args=(locations, pseudoranges))

        t = result.x[0]
        x = result.x[1]
        y = result.x[2]

        print('\nRESULT: ')

        print(f'\tx (meters): {x}')
        print(f'\ty (meters): {y}')
        print(f'\tt (seconds): {t}')

        # plot_prop(center, locations, x, y, t, pseudoranges=pseudoranges)
        
        location = self._meters_to_latlon(x, y, center)
        WebSocketSender.send({"Source": "Python-Dev", "client": {"Long": location[0], "Lat": location[1]}, "stations": [{"id": station.name, "Long": station.location[0], "Lat": station.location[1], "radius": (-pseudoranges[i])*299702458+t*299702458} for i, station in enumerate(good_stations)]})

        solution = {
            "location": location,
            "pseudoranges": pseudoranges,
            "t":t
        }

        return solution

    def _sparse_correlation(self, features, span, rxdata, minidx):    
        num_lags = span + len(rxdata) - 1

        intermediate_corr_length = len(rxdata) - 400 + 1
        corr = np.zeros(num_lags)
        
        for idx_offset in sorted(features.keys()):
                seg = features[idx_offset].FeatureData
                idx = idx_offset - minidx
                shift = idx - span
                
                intermediate_corr = np.zeros(intermediate_corr_length)
                intermediate_corr = np.abs(sg.correlate(rxdata, seg, mode='valid'))
                
                out_start = max(0, -shift)
                out_end = out_start + intermediate_corr_length

                corr[out_start:out_end] += intermediate_corr
        
        return corr

    def calculate_clock_offset(self, features_in, rx_signal, rx_start_time, fs):
        """Calculate the rough clock offset between the client and the reference receiver. This function
        uses a sparse correlation between the features and the received data to reduce the size of future 
        correlations

        :param features_in: input features from the reference receiver
        :type features_in: list[Feature]
        :param rx_signal: Baseband received signal
        :type rx_signal: array-like complex
        :param rx_start_time: Receive window start time in nanoseconds from the epoch
        :type rx_start_time: int
        :param fs: Sample rate in Hz. Used only for printed output.
        :type fs: float

        :returns: Clock offset.
        :rtype: float
        """        
        # get the features that are close (...1 second?) to the rx_start_time
        # rx_end_time = len(rx_signal) / fs * 1000000000 + rx_start_time #all times in nanoseconds

        rx_end_time = round(len(rx_signal) / self.fractional_fs_demod) + rx_start_time #all times in nanoseconds
        clock_uncertainty = 1000e6 #(nanoseconds, depends on the network)
        time_window = [rx_start_time - clock_uncertainty, rx_end_time + clock_uncertainty]
        features_that_i_have_data_for = {}
        max_idx = None
        min_idx = None
        max_timestamp = None
        for feature in features_in:
            if feature.timestamp > time_window[0] and feature.timestamp < time_window[1] - (self.FEATURE_LEN)/self.fractional_fs_demod:
                # sample_offset = int(np.round(((feature.timestamp - time_window[0])/1e9) * fs))
                sample_offset = round((feature.timestamp - time_window[0]) * self.fractional_fs_demod)
                features_that_i_have_data_for[sample_offset] = feature
                if(max_idx == None or max_idx < sample_offset):
                    max_idx = sample_offset
                if(max_timestamp == None or max_timestamp < feature.timestamp):
                    max_timestamp = feature.timestamp
                if(min_idx == None or min_idx > sample_offset):
                    min_idx = sample_offset


        # print(sorted(valid_features.keys()))

        corr = self._sparse_correlation(features_that_i_have_data_for, (max_idx-min_idx), rx_signal, min_idx)
        corr_diff = np.abs(corr[:-1] - corr[1:])

        tf = plt.figure()
        plt.plot(corr)
        plt.plot(corr_diff)

        print(f'Expected last idx time: {max_timestamp}')
        print(f'Actual Last timestamp location: {rx_start_time + np.argmax(corr)/fs*1e9}')
        print((max_timestamp - rx_start_time - round(np.argmax(corr)/self.fractional_fs_demod))/1e9)
        plt.savefig(f"Logs/clockoffset.png", dpi=300, bbox_inches='tight') 
        plt.close('all')
        # assert(self._check_corr(corr))
        if(self._check_corr(corr, corr_z_thres = 5)):
            # return max_timestamp - rx_start_time - round(np.argmax(corr)/self.fractional_fs_demod)
            return max_timestamp - rx_start_time - round(np.argmax(corr_diff)/self.fractional_fs_demod)
        else:
            return None


    def get_valid_features(self, features_in, rx_start_time, rx_samples, pad=5000):
        """Use the clock offset to drop features which fall outside of the receive window.

        :param features_in: Features from the reference receiver.
        :type features_in: list[Feature]
        :param rx_start_time: Receive window start time in nanoseconds from the epoch.
        :type rx_start_time: int
        :param rx_samples: Number of samples in the receive window.
        :type rx_samples: int
        :param pad: Half-width of the correlation. Defaults to 5000.
        :type pad: int, optional

        :return: A dictionary mapping StationIDs to valid features.
        :rtype: dict
        """        

        rx_end_time = round(rx_samples / self.fractional_fs_demod) + rx_start_time #all times in nanoseconds
        features_that_i_have_data_for = {}
        for stationid in features_in.keys():
            good_features_for_this_station = []
            pad_length = round(pad/self.fractional_fs_demod)
            for feature in features_in[stationid]:
                if (feature.timestamp > rx_start_time + pad_length and 
                            feature.timestamp < rx_end_time - (self.FEATURE_LEN)/self.fractional_fs_demod - pad_length):
                    sample_offset = round((feature.timestamp - rx_start_time) * self.ds_fractional_fs)
                    feature.index = sample_offset
                    good_features_for_this_station.append(feature)
            features_that_i_have_data_for[stationid] = good_features_for_this_station
        return features_that_i_have_data_for
    
    def get_lo_correction_from_features(self, rx_signal, features_in, num_lags = 40, phase_lags=40, pad=5000):
        """Calculate the local oscillator correction by tracking phase change across a single feature.

        :param rx_signal: Baseband received signal.
        :type rx_signal: array-like complex
        :param features_in: list of valid features.
        :type features_in: list[Feature]
        :param num_lags: Number of lags in the correlation. Defaults to 40.
        :type num_lags: int, optional
        :param phase_lags: Number of lags to include for each phase step. Defaults to 40.
        :type phase_lags: int, optional
        :param pad: Correlation pad length. Defaults to 5000.
        :type pad: int, optional

        :return: Local oscillator error in radians/second.
        :rtype: float
        """        
        corlen = 2*pad-num_lags+1
        phases = []
        corr_precorrection = np.zeros(corlen)
        idx = features_in[0].index//self.decimation
        for i in range(10):
            corr_precorrection += np.abs(sg.correlate(rx_signal[idx-pad+i*num_lags:pad+idx+i*num_lags],
                                            features_in[0].FeatureData[i*num_lags:(i+1)*num_lags], mode='valid'))

        phases = []
        corr1 = np.zeros(2*pad-phase_lags+1)
        for i in range(10):
            ncorr1 = sg.correlate(rx_signal[idx-pad+i*phase_lags:pad+idx+i*phase_lags],
                                            features_in[0].FeatureData[i*phase_lags:(i+1)*phase_lags], mode='valid')
            corr1 += np.abs(ncorr1)
            phases.append(np.angle(ncorr1[np.argmax(corr_precorrection)]))

        ptime = np.arange(len(phases))*phase_lags/self.fs_demod
        omega = np.polyfit(ptime, np.unwrap(phases), 1)[0] #This is fragile when the error is small
        return omega
    
    def get_lo_correction(self, data_bb):
        """Compute the LO offset by comparing the detected station center frequency to the known "true" station 
        reference frequency. The detected center frequency is calculated by convolving the PSD of the signal with 
        itself, and assumes a symmetric PSD.

        :param data_bb: Baseband signal data.
        :type data_bb: array-like complex

        :return: LO offset in radians/second.
        :rtype: float
        """        
        data_ft = np.fft.fftshift(np.abs(np.fft.fft(data_bb)))
        d_omega = self.fs_demod/len(data_ft)*2*np.pi
        cv = sg.convolve(data_ft, data_ft)
        return (np.argmax(cv) - len(cv)//2)*d_omega/2
    
    def get_best_station(self):
        """Identify the most powerful station.

        :return: Index of the most powerful station.
        :rtype: int
        """        
        MONITOR_LENGTH = 1000
        station_scores = np.mean(np.abs(self.baseband_data[:,:MONITOR_LENGTH]), axis=1)
        print(f'\tStation Scores: {station_scores}')
        return np.argmax(station_scores)
    
    def calculate_sample_rate_offset(self, rx_signal, features_in):
        """Calculate the sample rate offset by comparing the location of the correlation
        peak for features at the beginning and end of the receive window.

        :param rx_signal: Received baseband signal.
        :type rx_signal: array-like complex
        :param features_in: List of features.
        :type features_in: list[Feature]

        :return: resampling rate.
        :rtype: float
        """        
        pad = 500
        idx1 = features_in[0].index//self.decimation
        idx2 = features_in[-1].index//self.decimation

        corr1 = np.abs(sg.correlate(rx_signal[idx1-pad:pad+idx1],
                                            features_in[0].FeatureData, mode='valid'))

        corr2 = np.abs(sg.correlate(rx_signal[idx2-pad:pad+idx2],
                                            features_in[-1].FeatureData, mode='valid'))

        shift = np.argmax(np.abs(corr2)) - np.argmax(np.abs(corr1))
        delay = idx2-idx1
        resample_factor = (shift + delay)/delay

        return resample_factor
    
    def get_pseudorange(self, data_baseband, mfeatures, station_name=None):
        """Estimate a pseudorange for a single station using all of the valid features.

        :param data_baseband: baseband received data.
        :type data_baseband: array-like complex
        :param mfeatures: valid features for a single station.
        :type mfeatures: list[Feature]
        :param station_name: Station name for generating plots. Defaults to None.
        :type station_name: str, optional

        :return: the pseudorange.
        :rtype: float
        """        
        pad = 300
        corr = np.zeros((2*pad - self.FEATURE_LEN)*self.decimation + 1)
        # corr = np.zeros(201)
        tf, ax = plt.subplots(2,1)
        data_upsampled = sg.resample_poly(data_baseband, self.decimation, 1)
        for feature in mfeatures:
            feature_upsampled = sg.resample_poly(feature.FeatureData, self.decimation, 1)
            idx = feature.index + self.FEATURE_LEN //2 * self.decimation
            # data_upsampled = sg.resample_poly(data_baseband[idx-pad:pad+idx], 15, 1)
            # cri = sg.correlate(data_baseband[idx//20-pad:pad+idx//20],
            #                             feature.FeatureData, mode='valid')
            cri = sg.correlate(data_upsampled[idx-pad*self.decimation:pad*self.decimation+idx], feature_upsampled, mode='valid')
            ax[0].plot(np.abs(cri))
            corr += np.abs(cri)
            # for i in range(10):
            #     corr += np.abs(sg.correlate(data_baseband[idx-pad-input_shift-offset+i*40:pad+idx-input_shift-offset+i*40],
            #                             mfeatures[idx][i*40:(i+1)*40], mode='valid'))
        # plt.plot(np.abs(corr))
        sample = np.argmax(np.abs(corr))
        ax[1].plot(corr)
        # print(sample)
        # plt.legend([str(i) for i in range(10)])
        plt.savefig(f"Logs/{station_name}_pseudorange.png", dpi=300, bbox_inches='tight') 
        plt.close('all')
        if(self._check_corr(corr, corr_z_thres = 5.5)):
            return (sample-pad*self.decimation)/self.fs_demod/self.decimation
        else:
            return None
    
    def _latlon_to_meters(self, loc, ref):
        """Function for converting geographic coordinates to X/Y offset from a reference location.

        :param loc: Target location
        :type loc: list[latitude, longitude]
        :param ref: Reference location
        :type ref: list[latitude, longitude]

        :return: (x, y) offsets in meters
        :rtype: tuple
        """    
        R = 6371000 # Earth's radius in meters

        # Convert latitude and longitude from degrees to radians
        phi1 = np.radians(loc[0])
        delta_phi = np.radians(ref[0] - loc[0])
        delta_lambda = np.radians(ref[1] - loc[1])

        # North-South offset in meters
        y = delta_phi * R

        # East-West offset in meters
        x = delta_lambda * R * np.cos(phi1)

        return x, y
    
    def _meters_to_latlon(self, x, y, ref):
        """Function for generating latitude and longitude from x/y coordinates and a reference point.

        :param x: horizontal distance from reference in m.
        :type x: float
        :param y: vertical distance from reference in m.
        :type y: float
        :param ref: reference point coordinates.
        :type ref: list[latitude,longitude]

        :return: coordinates of the target point.
        :rtype: list[latitude, longitude]
        """        
        R = 6371000

        # Convert latitude and longitude from degrees to radians
        phi0 = np.radians(ref[0])
        delta_phi = y/R
        phi1 = phi0 + delta_phi
        delta_lambda = x/(R * np.cos(phi1))

        loc = [np.degrees(phi1), np.degrees(delta_lambda) + ref[1]]

        return loc
    
    def _check_corr(self, corr, corr_z_thres = 8):
        """Function for checking the existence of a high-SNR peak in a correlation.

        :param corr: The correlation
        :type corr: array-like complex
        :param corr_z_thres: Minimum z score required for correlation peaks. Defaults to 8.
        :type corr_z_thres: int, optional

        :return: True if the correlation contains a high-SNR peak.
        :rtype: bool
        """        
        cmax = np.max(np.abs(corr))
        cmean = np.mean(np.abs(corr))
        cval = (cmax - cmean)/np.std(corr)
        print(f'Corr Check: {cval}')
        return cval > corr_z_thres
    
    def plot_solve(self, t, x, y, center, ref_location, pseudoranges, locations):
        """Function for plotting solutions on a blank map.

        :param t: Time offset between client and reference receiver clocks.
        :type t: float
        :param x: Horizontal distance between solution and center in meters.
        :type x: float
        :param y: Vertical distance between solution and center in meters.
        :type y: float
        :param center: reference location for plotting
        :type center: list[Latitude, Longitude]
        :param ref_location: Location of the reference receiver.
        :type ref_location: list[latitude, longitude]
        :param pseudoranges: Pseudoranges in the same order as locations
        :type pseudoranges: list[float]
        :param locations: List of station locations
        :type locations: list[list[latitude, longitude]]
        """    
        tp, ax = plt.subplots()
        plt.plot(0,0,'o') #center
        #reference
        refloc = self.latlon_to_meters(center, ref_location)
        ax.plot(refloc[0], refloc[1], 'o')
        for i in range(len(locations)):
            ax.plot(locations[i][0], locations[i][1], 'ro')
            circle = plt.Circle((locations[i][0], locations[i][1]), 
                                (-pseudoranges[i])/400e3*self.C+t*self.C,
                                  color='r', fill=False)
            ax.add_patch(circle)

        plt.plot(x, y, 'go')
        # plt.show()
