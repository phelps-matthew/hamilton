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

    async def plot_spectrogram(self, data, sample_rate, ax):
        Pxx, freqs, bins, im = ax.specgram(data, NFFT=1024, Fs=sample_rate, window=np.hanning(1024), noverlap=512)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        return ax

    async def plot_psd(self, data, sample_rate, ax):
        ax.psd(data, NFFT=1024, Fs=sample_rate, window=np.hanning(1024))
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power/Frequency (dB/Hz)")
        return ax

    async def plot_doppler(self, kinematic_state_timeseries, center_freq, ax):
        times = [t[0] for t in kinematic_state_timeseries]
        range_rates = [t[1]["range_rate"] for t in kinematic_state_timeseries]
        speed_of_light = 299792.458  # km/s
        doppler_shifts = [-rr * center_freq / speed_of_light for rr in range_rates]
        t0 = times[0]
        times_seconds = [(t - t0).total_seconds() for t in times]
        ax.plot(times_seconds, doppler_shifts)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel(r"$\Delta f$ (Hz)")
        ax.grid(True)
        ax.set_ylim(-25000, 25000)
        return ax

    async def plot_orbit(self, kinematic_state_timeseries, azel_timeseries, ax):
        # Extract az and el from kinematic_state_timeseries
        ks_az = [np.radians(t[1]["az"]) for t in kinematic_state_timeseries]
        ks_el = [90 - t[1]["el"] for t in kinematic_state_timeseries]
        ks_times = [t[0] for t in kinematic_state_timeseries]

        # Extract az and el from azel_timeseries
        azel_az = [np.radians(t[1]["azimuth"]) for t in azel_timeseries]
        azel_el = [90 - t[1]["elevation"] for t in azel_timeseries]
        azel_times = [t[0] for t in azel_timeseries]

        # Plot kinematic state series with smaller points
        ax.plot(ks_az, ks_el, "o-", label="Orbit", markersize=2)

        # Plot azel series with smaller points
        ax.plot(azel_az, azel_el, "o-", label="Mount", markersize=2)

        # Set the azimuth labels
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_thetagrids(np.arange(0, 360, 45), [f"{i}°" for i in range(0, 360, 45)])

        # Set the elevation labels along the horizontal axis
        ax.set_yticks(np.arange(0, 91, 15))
        ax.set_yticklabels([f"{90-e}°" for e in np.arange(0, 91, 15)])
        ax.set_ylim(0, 90)

        # Add AOS and LOS labels and larger points
        all_times = ks_times + azel_times
        aos_time = min(all_times)
        los_time = max(all_times)

        aos_index = all_times.index(aos_time)
        los_index = all_times.index(los_time)

        if aos_index < len(ks_times):
            aos_az = kinematic_state_timeseries[aos_index][1]["az"]
            aos_el = kinematic_state_timeseries[aos_index][1]["el"]
        else:
            aos_az = azel_timeseries[aos_index - len(ks_times)][1]["azimuth"]
            aos_el = azel_timeseries[aos_index - len(ks_times)][1]["elevation"]

        if los_index < len(ks_times):
            los_az = kinematic_state_timeseries[los_index][1]["az"]
            los_el = kinematic_state_timeseries[los_index][1]["el"]
        else:
            los_az = azel_timeseries[los_index - len(ks_times)][1]["azimuth"]
            los_el = azel_timeseries[los_index - len(ks_times)][1]["elevation"]

        # Determine quadrants and annotation positions
        def get_quadrant(az):
            az = az % 360
            if 0 <= az <= 90:
                return 1
            elif 90 < az <= 180:
                return 4
            elif 180 < az <= 270:
                return 3
            else:
                return 2

        def get_annotation_pos(quadrant, clockwise):
            if quadrant == 1:
                return (-8, 8) if clockwise else (8, 8)
            elif quadrant == 2:
                return (-8, -8) if clockwise else (-8, 8)
            elif quadrant == 3:
                return (8, -8) if clockwise else (-8, -8)
            else:
                return (8, -8) if clockwise else (-8, -8)

        aos_quadrant = get_quadrant(aos_az)
        los_quadrant = get_quadrant(los_az)
        clockwise = (los_az - aos_az) % 360 <= 180

        aos_annotation_pos = get_annotation_pos(aos_quadrant, clockwise)
        los_annotation_pos = get_annotation_pos(los_quadrant, clockwise)

        ax.annotate(
            "AOS",
            xy=(np.radians(aos_az), 90 - aos_el),
            xytext=aos_annotation_pos,
            textcoords="offset points",
            ha="center",
            va="center",
            size=8,
        )
        ax.annotate(
            "LOS",
            xy=(np.radians(los_az), 90 - los_el),
            xytext=los_annotation_pos,
            textcoords="offset points",
            ha="center",
            va="center",
            size=8,
        )

        # ax.legend(loc="upper right")
        ax.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1), fontsize="small")

        return ax

    async def plot_panel(self, sigmf_file, filename):
        logger.info(f"Plotting panel for {filename}")
        kinematic_state_timeseries, azel_timeseries = await self.extract_annotation_timeseries(sigmf_file)
        center_freq = sigmf_file.get_global_field(sigmf.SigMFFile.FREQUENCY_KEY)
        samples = sigmf_file.read_samples()
        sample_rate = sigmf_file.get_global_field(sigmf.SigMFFile.SAMPLE_RATE_KEY)

        # Create a figure with a 2x2 grid, with a 4:1 ratio between the first and second column
        # fig = plt.figure(figsize=(1.0 * 20, 1.0 * 7.5))
        fig = plt.figure(figsize=(16, 9))
        gs = fig.add_gridspec(2, 2, width_ratios=[4, 1], height_ratios=[3, 2])

        # Spectrogram
        ax_spectrogram = fig.add_subplot(gs[0, 0])
        ax_spectrogram = await self.plot_spectrogram(samples, sample_rate, ax_spectrogram)
        ax_spectrogram.set_title("Spectrogram")

        # PSD
        ax_psd = fig.add_subplot(gs[1, 1])
        ax_psd = await self.plot_psd(samples, sample_rate, ax_psd)
        ax_psd.set_title("Power Spectral Density")

        # Doppler
        ax_doppler = fig.add_subplot(gs[1, 0])
        ax_doppler = await self.plot_doppler(kinematic_state_timeseries, center_freq, ax_doppler)
        ax_doppler.set_title("Doppler Shift")

        # Orbit
        ax_orbit = fig.add_subplot(gs[0, 1], projection="polar")
        ax_orbit = await self.plot_orbit(kinematic_state_timeseries, azel_timeseries, ax_orbit)
        ax_orbit.set_title("Orbit")

        # Adjust layout and save
        fig.tight_layout()
        fig.savefig(filename, dpi=400, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Finished plotting panel for {filename}")

    async def plot_panels(self, force_replot=False):
        for data_file in self.observations_dir.glob("*.sigmf-data"):
            panel_filename = self.panels_dir / f"{data_file.stem}_panel.png"
            if not panel_filename.exists() or force_replot:
                meta_file = data_file.with_suffix(".sigmf-meta")
                with open(meta_file) as f:
                    metadata = json.load(f)
                sigmf_file = sigmf.SigMFFile(metadata=metadata, data_file=data_file, skip_checksum=True)
                await self.plot_panel(sigmf_file, panel_filename)

    #async def plot_psds(self, force_replot=False):
    #    for data_file in self.observations_dir.glob("*.sigmf-data"):
    #        psd_filename = self.psd_dir / f"{data_file.stem}_psd.png"
    #        if not psd_filename.exists() or force_replot:
    #            meta_file = data_file.with_suffix(".sigmf-meta")
    #            with open(meta_file) as f:
    #                metadata = json.load(f)
    #            smf = sigmf.SigMFFile(metadata=metadata, data_file=data_file, skip_checksum=True)
    #            samples = smf.read_samples()
    #            await self.plot_psd(samples, smf.get_global_field(sigmf.SigMFFile.SAMPLE_RATE_KEY), psd_filename)

    #async def plot_spectrograms(self, force_replot=False):
    #    for data_file in self.observations_dir.glob("*.sigmf-data"):
    #        spectrogram_filename = self.spectrogram_dir / f"{data_file.stem}_spectrogram.png"
    #        if not spectrogram_filename.exists() or force_replot:
    #            meta_file = data_file.with_suffix(".sigmf-meta")
    #            with open(meta_file) as f:
    #                metadata = json.load(f)
    #            smf = sigmf.SigMFFile(metadata=metadata, data_file=data_file, skip_checksum=True)
    #            samples = smf.read_samples()
    #            await self.plot_spectrogram(
    #                samples, smf.get_global_field(sigmf.SigMFFile.SAMPLE_RATE_KEY), spectrogram_filename
    #            )
