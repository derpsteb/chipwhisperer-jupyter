import chipfail_lib
import serial
import Setup_Generic

import matplotlib.pyplot as plt
import random
import datetime
from time import sleep
import json
import base64

PROGRESS_FILE = "progress.txt"
cur_time = datetime.datetime.now()
LOG_FILE = f"{cur_time.strftime('%d%m%y_%X')}.log"

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

def collect_trace_basic():
    scope.io.tio1 = "gpio_low"
    scope.arm()
    
    # As long as only the A7's power port is connected to reset this will issue a 1us reset
    # The CW can trigger on the reset release
    chipfail_lib.manual_glitch(fpga)
    
    scope.io.tio1 = "gpio_high"
    # scope.capture()
    # return scope.get_last_trace()

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

def save_progress(progress):
    with open(PROGRESS_FILE, "w+") as file:
        file.truncate(0)
        file.write(json.dumps(progress))

def save_log(log):
    with open(LOG_FILE, "w+b") as file:
        file.truncate(0)
        file.write(json.dumps(log, ensure_ascii=False).encode())

if __name__ == "__main__":

    SCOPETYPE = 'OPENADC'
    PLATFORM = 'CWLITEXMEGA'
    CRYPTO_TARGET = 'AVRCRYPTOLIB'

    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB1", baudrate=115200)
    target = serial.Serial("/dev/ttyUSB2", baudrate=115200, timeout=0.2)

    offset = 0
    nr_samples = 24400
    
    setup_basic(scope, offset, nr_samples)
    setup_glitcher(scope)
    chipfail_lib.setup(fpga)
    scope.adc.decimate = 100

    # 50x downsampling: 300*50 = 15.000. 1 cycle = 34ns --> 510.000 ns = 510 us
    MIN_OFFSET = 2536000
    MAX_OFFSET = 2601000
    STEP_SIZES = [5, 2, 1]
    
    WIDTH = 1260
    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, WIDTH)

    success = False
    offsets = range(MIN_OFFSET, MAX_OFFSET)
    try:
        progress = read_progress()
    except:
        with open(PROGRESS_FILE, "w"):
            pass
        progress = {"step_size": 0, "cur_repeat": 0, "used_offsets": []}

    log = {"used_offsets": [], "used_widths": [], "responses": []}
    used_len = len(progress["used_offsets"])
    print(f"starting with progress len: {used_len}")

    try:
        # increase search resolution from time to time
        for step_size in STEP_SIZES:
            progress["step_size"] = step_size
            # only decrease step_size after repeating 20 times
            for i in range(0,20):
                progress["cur_repeat"] = i

                offsets = set(range(MIN_OFFSET, MAX_OFFSET+1, step_size))
                new_offsets = list(offsets.difference(set(progress)))
                random.shuffle(new_offsets)

                for offset in new_offsets:
                    time_pre = datetime.datetime.now()

                    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_DELAY, offset)

                    trace = collect_trace_basic()    
                    # plt.plot(trace)
                    # plt.show()
                    success, timeout, response = chipfail_lib.success_uart(target, offset, WIDTH, b"Open\r\n", False)
                    if success:
                        exit(0)
                    chipfail_lib.flush_uart(target)

                    # chipfail_lib.wait_until_rdy(fpga)
                    
                    progress["used_offsets"].append(offset)
                    log["used_widths"].append(WIDTH)
                    log["used_offsets"].append(offset)
                    log["responses"].append(base64.b64encode(response).decode())

                    sleep(0.1)    
                    print(f"\tcurrent time/it: {datetime.datetime.now() - time_pre}")

                # Remove any leftover progress from FS
                with open(PROGRESS_FILE, "w+") as file:
                    file.truncate(0)
                progress["used_offsets"] = []

    except Exception:
        print("unknown exception:")
        print(traceback.format_exc())
    finally:
        save_progress(progress)
        save_log(log)
