from terra_dsp import Feature
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def plot_signal_timing(features, rx_length, fs, rx_start, ax = None, show=True):
    """Plots a graph showing the received signal section and the position of features.

    :param features: Dictionary mapping StationIDs to Feature objects
    :type features: dict
    :param rx_length: Received signal length in seconds.
    :type rx_length: float
    :param fs: Sample rate
    :type fs: float
    :param rx_start: Start of rx window.
    :type rx_start: float
    :param ax: Axes for plotting. Created if None.
    :type ax: matplotlib.axes, optional
    :param show: If True, call plt.show(). Defaults to True.
    :type show: bool, optional
    """    
    if ax is None:
        sig, ax = plt.subplots()
    ax.autoscale(enable=True, axis='both', tight=None)
    ax.plot(0,0)
    rx_dur = rx_length / fs
    print(len(features))
    #plot the rx signal window
    ax.add_patch(Rectangle((0, 0), rx_dur, 0.5))
    y_offset = 0
    for featureStation in features.values():
        for feature in featureStation:
            start_offset = (feature.timestamp - rx_start)/1e9
            ax.add_patch(Rectangle((start_offset, 0.6+y_offset), 400/50000, 0.5, facecolor='red'))
        y_offset = y_offset+0.6

    if(show):
        plt.show()

def plot_prop(center, locations, x = None, y = None, t = None, ref_location = None, pseudoranges = None, prop_delays = None):
    """Function for plotting solutions on a blank map.

    :param center: reference location for plotting
    :type center: list[Latitude, Longitude]
    :param locations: List of station locations
    :type locations: list[list[Latitude, Longitude]]
    :param x: Horizontal distance between solution and center in meters. Defaults to None.
    :type x: float, optional
    :param y: Vertical distance between solution and center in meters. Defaults to None.
    :type y: float, optional
    :param t: Time offset between client and reference receiver clocks. Defaults to None.
    :type t: float, optional
    :param ref_location: Location of the reference receiver. Defaults to None.
    :type ref_location: list[Latitude, Longitude], optional
    :param pseudoranges: Pseudoranges in the same order as locations. Defaults to None.
    :type pseudoranges: list[float], optional
    :param prop_delays: For plotting propagation without a solve. Propagation length from station to reference receiver. Defaults to None.
    :type prop_delays: list[float], optional
    """    
    C = 299702458

    tp, ax = plt.subplots()
    plt.plot(0,0,'o') #center
    #reference
    if(ref_location is not None):
        refloc = _latlon_to_meters(center, ref_location)
        ax.plot(refloc[0], refloc[1], 'o')
        
    for i in range(len(locations)):
        ax.plot(locations[i][0], locations[i][1], 'ro')
        if(pseudoranges is not None):
            circle = plt.Circle((locations[i][0], locations[i][1]), 
                                (-pseudoranges[i])*C+t*C,
                                color='r', fill=False)
        elif(prop_delays is not None):
            circle = plt.Circle((locations[i][0], locations[i][1]), 
                                prop_delays[i]*C,
                                color='r', fill=False)
        ax.add_patch(circle)

    if(x is not None):
        plt.plot(x, y, 'go')
    plt.show()

def _latlon_to_meters(loc, ref):
    """Function for converting geographic coordinates to X/Y offset from a reference location.

    :param loc: Target location
    :type loc: list[Latitude, Longitude]
    :param ref: Reference location
    :type ref: list[Latitude, Longitude]

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