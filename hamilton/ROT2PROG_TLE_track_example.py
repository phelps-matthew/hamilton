import rot2prog
import logging


logging.basicConfig(level = logging.DEBUG)

if __name__ == "__main__":
    rot = rot2prog.ROT2Prog('/dev/usbttymd01')
    rot.status()
    #print(sat_db_dict)
    #rot.set(0, 0)
    #rot.stop()
    #rot.set(12.63, 10.49)
