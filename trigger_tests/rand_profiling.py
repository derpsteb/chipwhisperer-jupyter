import chipfail_lib
import serial
import Setup_Generic

import matplotlib.pyplot as plt
import random
import datetime
from time import sleep
import sys
import traceback
import base64
import json

cur_time = datetime.datetime.now()
PROGRESS_FILE = f"{cur_time.strftime('%d%m%y_%X')}_profiling.log"

def setup_cw(scope, offset, nr_samples):
    scope.default_setup()
    scope.adc.offset = offset
    scope.gain.gain = 50
    scope.adc.samples = nr_samples
    #scope.adc.presamples = 400
    
    # per docs has to be like that for DecodeIO and SAD
    scope.adc.basic_mode = "rising_edge"

def setup_basic(scope, offset, nr_samples):
    setup_cw(scope, offset, nr_samples)

    scope.adc.basic_mode = "rising_edge"
    scope.trigger.module = "basic"
    scope.trigger.triggers = "tio4"

def reset_tio1():
    scope.io.tio1 = "gpio_low"
    sleep(0.1)
    scope.io.tio1 = "gpio_high"
    sleep(0.2)


def collect_trace_basic():
    scope.io.tio1 = "gpio_low"
    scope.arm()
    
    # As long as only the A7's power port is connected to reset this will issue a 1us reset
    # The CW can trigger on the reset release
    chipfail_lib.manual_glitch(fpga)
    
    scope.io.tio1 = "gpio_high"
    scope.capture()
    return scope.get_last_trace()

def setup_glitcher(scope, offset=0, width=1):
    scope.glitch.clk_src = "clkgen"
    # scope.glitch.width = 10
    # scope.glitch.width_fine = 0
    scope.glitch.repeat = width
    scope.glitch.ext_offset = offset
    scope.glitch.trigger_src = "ext_single"
    scope.glitch.output = "enable_only"
    scope.glitch.arm_timing = 'before_scope'

    scope.io.glitch_hp = True
    scope.io.glitch_lp = False

def read_progress():
    with open(PROGRESS_FILE, "r") as file:
        return json.loads(file.read())

def save_progress(log):
    with open(PROGRESS_FILE, "w+") as file:
        file.truncate(0)
        file.write(json.dumps(log))

if __name__ == "__main__":

    SCOPETYPE = 'OPENADC'
    PLATFORM = 'CWLITEXMEGA'
    CRYPTO_TARGET = 'AVRCRYPTOLIB'

    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB2", baudrate=115200)
    target = serial.Serial("/dev/ttyUSB0", baudrate=115200, timeout=0.2)

    offset = 0
    nr_samples = 24400
    
    setup_basic(scope, offset, nr_samples)
    setup_glitcher(scope)
    chipfail_lib.setup(fpga)
    scope.adc.decimate = 50

    # 50x downsampling: 300*50 = 15.000. 1 cycle = 34ns --> 510.000 ns = 510 us
    MIN_OFFSET = 788
    MAX_OFFSET = 789
    STEP_SIZES = [50, 20, 10, 5, 2, 1]
    OFFSET_REPEAT = 20
    
    MIN_WIDTH = 100
    MAX_WIDTH = 200
    WIDTH_STEPS = 10
    WIDTH_REPEAT = 20

    width_repeat = 0

    success_ctr = 0
    try_ctr = 0
    success = False
    offsets = range(MIN_OFFSET, MAX_OFFSET)
    try:
        progress = read_progress()
    except:
        with open(PROGRESS_FILE, "w"):
            pass
        progress_l = [{"step_size": 0, "cur_repeat": 0, "used_offsets": [], "used_widths": [], "responses": []}]
        progress = progress_l[0]

    widths = set(range(MIN_WIDTH, MAX_WIDTH, WIDTH_STEPS))
    widths = list(widths.difference(progress["used_widths"]))
    # widths = [1440, 1450, 1460, 1470]

    random.shuffle(widths)
    widths_iter = iter(widths)
    width = next(widths_iter)
    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, width)

    used_len = len(progress["used_offsets"])
    print(f"starting with progress len: {used_len}")

    try:
        # increase search resolution from time to time
        for step_size in STEP_SIZES:
            progress["step_size"] = step_size
            # only decrease step_size after repeating 20 times
            for i in range(0,OFFSET_REPEAT):
                progress["cur_repeat"] = i

                offsets = set(range(MIN_OFFSET, MAX_OFFSET+1, step_size))
                new_offsets = list(offsets.difference(set(progress)))
                # new_offsets = [784, 787, 788, 794, 804, 812, 812, 822, 842, 846, 850, 858, 859]
                random.shuffle(new_offsets)

                for offset in new_offsets:
                    time_pre = datetime.datetime.now()

                    width_repeat += 1
                    if width_repeat >= WIDTH_REPEAT:
                        try:
                            width = next(widths_iter)
                        except StopIteration:
                            widths_iter = iter(widths)
                            width = next(widths_iter)

                        chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, width)
                        width_repeat = 0

                    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_DELAY, offset)

                    trace = collect_trace_basic()
                    try_ctr += 1   
                    # plt.plot(trace)
                    # plt.show()
                    success, timeout, response = chipfail_lib.success_uart(target, offset, width, b'target_ptr: 2200100 | val: aa\n', False)
                    if timeout:
                        chipfail_lib.flush_uart(target)
                        reset_tio1()

                    if success:
                        print("success?")
                        success_ctr += 1
                    chipfail_lib.flush_uart(target)
                    
                    progress["used_widths"].append(width)
                    progress["used_offsets"].append(offset)
                    progress["responses"].append(base64.b64encode(response).decode())

                    # sleep(0.1)    
                    # Don't wait for A7 atm since it sometimes continously reports status `16`
                    # I don't know where this comes from but missing one or two glitches is better than hanging.
                    # chipfail_lib.wait_until_rdy(fpga)
                    print(f"\tcurrent time/it: {datetime.datetime.now() - time_pre}")

                # Remove any leftover progress from FS
                with open(PROGRESS_FILE, "w+") as file:
                    file.truncate(0)
                progress_l.append(progress)
                progress = {"step_size": 0, "cur_repeat": 0, "used_offsets": [], "used_widths": [], "responses": []}

    except KeyboardInterrupt:
        pass
    except Exception:
        print("unknown exception:")
        print(traceback.format_exc())
    finally:
        print(f"tries: {try_ctr}")
        print(f"success: {success_ctr}")
        save_progress(progress_l)
