from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    COMMAND_QUEUE = "sdr_commands"
    STATUS_QUEUE = "sdr_status"

    RX_GAIN_DEFAULT = 40 
    SAMPLE_RATE = 50000
    CH0_ANTENNA_VHF = "TX/RX"
    CH0_ANTENNA_UHF = "RX2"
    VHF_FREQ_DEFAULT = 140000000
    UHF_FREQ_DEFAULT = 425000000
