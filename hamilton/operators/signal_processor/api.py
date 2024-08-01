import asyncio
import json
import logging
from pathlib import Path

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
        self.psd_dir.mkdir(exist_ok=True, parents=True)
        self.spectrogram_dir.mkdir(exist_ok=True, parents=True)

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
