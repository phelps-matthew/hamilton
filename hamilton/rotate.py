import rot2prog
import logging

# Uncomment the following line if you need logging
# logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    rot = rot2prog.ROT2Prog('/dev/usbttymd01')
    rot.set_limits(min_az=0, max_az=540, min_el=10, max_el=170)

    print("-" * 30)
    print("commands:\ns = status\nset x y = set az (deg) el (deg)\nstop = abort rotation\nlimits = get rotation limits\nq = quit")
    print("-" * 30)

    while True:
        user_input = input("rotator control: ").strip()

        if user_input == 's':
            print(f"position (degrees): {rot.status()}")
        elif user_input.startswith('set '):
            try:
                _, x_str, y_str = user_input.split()
                x, y = float(x_str), float(y_str)
                print(f"setting az/el to ({x}, {y})...")
                rot.set(x, y)
            except ValueError as e:
                print(f"Invalid input for set command: {e}")
        elif user_input == 'stop':
            print("stopping rotators...")
            rot.stop()
        elif user_input == 'limits':
            print("Getting rotation limits...")
            print(rot.get_limits())
        elif user_input == 'q':
            print("Quitting application...")
            break
        else:
            print("Unrecognized command.")
