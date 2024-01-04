import matplotlib.pyplot as plt
import pandas as pd
import pvlib
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem

coordinates = [
    (32.2, -111.0, "Tucson", 700, "Etc/GMT+7"),
    (35.1, -106.6, "Albuquerque", 1500, "Etc/GMT+7"),
    (37.8, -122.4, "San Francisco", 10, "Etc/GMT+8"),
    (52.5, 13.4, "Berlin", 34, "Etc/GMT-1"),
]


cec_modules = pvlib.pvsystem.retrieve_sam("CECMod")

sapm_inverters = pvlib.pvsystem.retrieve_sam("CECInverter")

module = cec_modules["Canadian_Solar_CS5P_220M___2009_"]

inverter = sapm_inverters["ABB__MICRO_0_25_I_OUTD_US_208__208V_"]

temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"]

tmys = []

for location in coordinates:
    latitude, longitude, name, altitude, timezone = location
    weather = pvlib.iotools.get_pvgis_tmy(latitude, longitude)[0]
    weather.index.name = "utc_time"
    tmys.append(weather)

energies = {}

for location, weather in zip(coordinates, tmys):
    latitude, longitude, name, altitude, timezone = location
    location = Location(
        latitude,
        longitude,
        name=name,
        altitude=altitude,
        tz=timezone,
    )
    mount = FixedMount(surface_tilt=latitude, surface_azimuth=180)
    array = Array(
        mount=mount,
        module_parameters=module,
        temperature_model_parameters=temperature_model_parameters,
    )
    system = PVSystem(arrays=[array], inverter_parameters=inverter)
    mc = ModelChain(system, location)
    mc.run_model(weather)
    annual_energy = mc.results.ac.sum()
    energies[name] = annual_energy


energies = pd.Series(energies)


print(energies)


energies.plot(kind="bar", rot=0)


plt.ylabel("Yearly energy yield (W hr)")

plt.show()
