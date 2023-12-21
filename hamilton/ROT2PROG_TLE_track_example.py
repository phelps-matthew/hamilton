import rot2prog
import logging
from passive_rf.db.gen_sat_db import generate_db


logging.basicConfig(level = logging.DEBUG)

if __name__ == "__main__":
    sat_db_dict = generate_db()
    rot = rot2prog.ROT2Prog('/dev/usbtty1')
    rot.status()
    #print(sat_db_dict)
    #rot.set(0, 0)
    #rot.stop()
    #rot.set(12.63, 10.49)