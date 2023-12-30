import rot2prog
import logging

#logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    rot = rot2prog.ROT2Prog('/dev/usbttymd01')
    print("-" * 30)
    print("commands:\ns = status\nset x y = set az (deg) el (deg)\nstop = abort rotation")
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
        else:
            print("Unrecognized command.")
