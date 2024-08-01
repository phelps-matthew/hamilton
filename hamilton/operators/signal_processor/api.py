import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime as dt, timedelta

import matplotlib.pyplot as plt
import numpy as np
import sigmf

from hamilton.operators.signal_processor.config import SignalProcessorControllerConfig

logger = logging.getLogger(__name__)


class SignalProcessor:
    def __init__(self, config: SignalProcessorControllerConfig):
        self.config = config
        # make dirs
        self.observations_dir = Path(self.config.observations_dir).expanduser()

        self.psd_dir = self.observations_dir / "psd"
        self.spectrogram_dir = self.observations_dir / "spectrogram"
        self.panels_dir = self.observations_dir / "panels"

        self.psd_dir.mkdir(exist_ok=True, parents=True)
        self.spectrogram_dir.mkdir(exist_ok=True, parents=True)
        self.panels_dir.mkdir(exist_ok=True, parents=True)

        self.sigmf_file = None

    async def extract_annotation_timeseries(self, sigmf_file: sigmf.SigMFFile):
        annotations = sigmf_file.get_annotations()
        sample_rate = sigmf_file.get_global_field(sigmf.SigMFFile.SAMPLE_RATE_KEY)
        t0 = dt.fromisoformat(sigmf_file.get_captures()[0]["core:datetime"])

        kinematic_state_timeseries = []
        azel_timeseries = []

        for a in annotations:
            t = t0 + timedelta(seconds=a["core:sample_start"] / sample_rate)
            if "custom:kinematic_state" in a:
                kinematic_state_timeseries.append((t, a["custom:kinematic_state"]))
            if "custom:azel" in a:
                azel_timeseries.append((t, a["custom:azel"]))

        # Remove duplicates, keeping the later index
        kinematic_state_timeseries = list({t: v for t, v in reversed(kinematic_state_timeseries)}.items())
        azel_timeseries = list({t: v for t, v in reversed(azel_timeseries)}.items())

        # Sort the timeseries by time
        kinematic_state_timeseries.sort(key=lambda x: x[0])
        azel_timeseries.sort(key=lambda x: x[0])

        return kinematic_state_timeseries, azel_timeseries

    async def plot_psd(self, data, sample_rate, filename):
        logger.info(f"Plotting PSD for {filename}")
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.psd(data, NFFT=1024, Fs=sample_rate, window=np.hanning(1024))
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power/Frequency (dB/Hz)")
        base_filename = Path(filename).stem
        ax.set_title(f"Power Spectral Density - {base_filename}")
        fig.savefig(filename, dpi=400)
        plt.close()
        del fig
        logger.info(f"Finished plotting PSD for {filename}")

    async def plot_spectrogram(self, data, sample_rate, filename):
        logger.info(f"Plotting spectrogram for {filename}")
        fig, ax = plt.subplots(figsize=(10, 6))
        Pxx, freqs, bins, im = plt.specgram(data, NFFT=1024, Fs=sample_rate, window=np.hanning(1024), noverlap=512)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        base_filename = Path(filename).stem
        ax.set_title(f"Spectrogram - {base_filename}")
        fig.savefig(filename, dpi=400)
        plt.close()
        del fig
        logger.info(f"Finished plotting spectrogram for {filename}")

    async def plot_orbit(self, kinematic_state_timeseries, azel_timeseries, filename):
        logger.info(f"Plotting orbit for {filename}")
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection="polar"))

        # Extract az and el from kinematic_state_timeseries
        ks_az = [np.radians(90 - t[1]["az"]) for t in kinematic_state_timeseries]
        ks_el = [90 - t[1]["el"] for t in kinematic_state_timeseries]

        # Extract az and el from azel_timeseries
        azel_az = [np.radians(90 - t[1]["azimuth"]) for t in azel_timeseries]
        azel_el = [90 - t[1]["elevation"] for t in azel_timeseries]

        # Plot kinematic state series
        ax.plot(ks_az, ks_el, "o-", label="Orbit")

        # Plot azel series
        ax.plot(azel_az, azel_el, "o-", label="Mount")

        # Set the azimuth labels
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_thetagrids(np.arange(0, 360, 45), ["N", "NE", "E", "SE", "S", "SW", "W", "NW"])

        # Set the elevation labels
        ax.set_rgrids(np.arange(0, 91, 15), labels=[f"{90-e}°" for e in np.arange(0, 91, 15)])
        ax.set_ylim(0, 90)

        ax.set_title("Orbit Plot (Azimuth/Elevation)")
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

        fig.savefig(filename, dpi=400, bbox_inches="tight")
        plt.close()
        del fig
        logger.info(f"Finished plotting orbit for {filename}")

    async def plot_doppler(self, kinematic_state_timeseries):
        pass

    async def plot_panel(self, sigmf_file, filename):
        kinematic_state_timeseries, azel_timeseries = await self.extract_annotation_timeseries(sigmf_file)

        # Plot orbit
        orbit_filename = self.panels_dir / f"{Path(filename).stem}_orbit.png"
        await self.plot_orbit(kinematic_state_timeseries, azel_timeseries, orbit_filename)

    async def plot_panels(self, force_replot=False):
        for data_file in self.observations_dir.glob("*.sigmf-data"):
            panel_filename = self.panels_dir / f"{data_file.stem}_panel.png"
            if not panel_filename.exists() or force_replot:
                meta_file = data_file.with_suffix(".sigmf-meta")
                with open(meta_file) as f:
                    metadata = json.load(f)
                sigmf_file = sigmf.SigMFFile(metadata=metadata, data_file=data_file, skip_checksum=True)
                await self.plot_panel(sigmf_file, panel_filename)

    async def plot_psds(self, force_replot=False):
        for data_file in self.observations_dir.glob("*.sigmf-data"):
            psd_filename = self.psd_dir / f"{data_file.stem}_psd.png"
            if not psd_filename.exists() or force_replot:
                meta_file = data_file.with_suffix(".sigmf-meta")
                with open(meta_file) as f:
                    metadata = json.load(f)
                smf = sigmf.SigMFFile(metadata=metadata, data_file=data_file, skip_checksum=True)
                samples = smf.read_samples()
                await self.plot_psd(samples, smf.get_global_field(sigmf.SigMFFile.SAMPLE_RATE_KEY), psd_filename)

    async def plot_spectrograms(self, force_replot=False):
        for data_file in self.observations_dir.glob("*.sigmf-data"):
            spectrogram_filename = self.spectrogram_dir / f"{data_file.stem}_spectrogram.png"
            if not spectrogram_filename.exists() or force_replot:
                meta_file = data_file.with_suffix(".sigmf-meta")
                with open(meta_file) as f:
                    metadata = json.load(f)
                smf = sigmf.SigMFFile(metadata=metadata, data_file=data_file, skip_checksum=True)
                samples = smf.read_samples()
                await self.plot_spectrogram(
                    samples, smf.get_global_field(sigmf.SigMFFile.SAMPLE_RATE_KEY), spectrogram_filename
                )
