import pandas as pd
from astropy.coordinates import EarthLocation, AltAz, get_sun
from astropy.time import Time
import numpy as np
from datetime import datetime, timedelta
from pytz import timezone
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pgf import FigureCanvasPgf

def solar_angle(longitude, latitude, year, month, day):
    location = EarthLocation(lon=longitude, lat=latitude, height=103.8)
    #tz_name = get_timezone(longitude, latitude)
    #tz = timezone(tz_name)
    tz = timezone('HST')
    results = {'Month': [], 'Azimuth (degrees)': [], 'Elevation (degrees)': []}

    for m in range(1, 13):
        az_values = []
        el_values = []

        for d in range(1, 32):
            try:
                date_time = datetime(year, m, d, 12, 0, 0) # Noon
                date_time = tz.localize(date_time)
                delta = timedelta(minutes=30)
                #import ipdb; ipdb.set_trace()
                times = Time([date_time + i*delta for i in range(-4, 5)], scale='utc')
                #times = Time([date_time + 0*delta for i in range(-4, 5)], scale='utc')
                altaz_frame = AltAz(obstime=times, location=location)
                sun_altaz = get_sun(times).transform_to(altaz_frame)

                az_values.append(np.mean(sun_altaz.az.deg))
                el_values.append(np.mean(sun_altaz.alt.deg))
            except Exception as e:
                continue

        results['Month'].append(month_name(m))
        results['Azimuth (degrees)'].append(np.mean(az_values))
        results['Elevation (degrees)'].append(np.mean(el_values))

    df = pd.DataFrame(results)
    print(df)
    return df

def month_name(month_num):
    return datetime(year=1, month=month_num, day=1).strftime("%B")

def save_latex_table_as_png(df, filename):
    latex_code = df.to_latex(index=False)
    
    # Create a new figure
    fig, ax = plt.subplots(figsize=(10, 2))

    # Hide axes
    ax.axis('off')

    # Add a table with the LaTeX code
    plt.text(0, 0.5, '\\begin{tabular}{lrr}\n' + latex_code + '\n\\end{tabular}', usetex=True)

    # Create a PGF backend canvas
    canvas = FigureCanvasPgf(fig)
    canvas.print_png(filename)
    plt.close()

# Example Usage:
longitude = -156.4314700000 # degrees
latitude = 20.7464000000 # degrees
year = 2023
month = 8
day = 14
df = solar_angle(longitude, latitude, year, month, day)
print(f"Az mean: {df['Azimuth (degrees)'].mean()}")
print(f"El mean: {df['Elevation (degrees)'].mean()}")

#save_latex_table_as_png(df, 'solar_table.png')