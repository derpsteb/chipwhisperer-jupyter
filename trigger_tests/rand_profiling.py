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
import chipwhisperer as cw
from chipwhisperer.common.traces import Trace


cur_time = datetime.datetime.now()
PROGRESS_FILE = f"{cur_time.strftime('%d%m%y_%X')}_profiling.log"

def load_bitstream(bitstream_file):
    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    scope.scopetype.cwFirmwareConfig[0xACE2].loader.setFPGAMode("debug")
    scope.scopetype.cwFirmwareConfig[0xACE2].loader._bsLoc = bitstream_file
    scope.scopetype.cwFirmwareConfig[0xACE2].loader.save_bsLoc()
    print("Mode: " + str(scope.scopetype.cwFirmwareConfig[0xACE2].loader._release_mode))
    print("Mode: " + str(scope.scopetype.cwFirmwareConfig[0xACE2].loader.fpga_bitstream()))
    input("powercycle done?")
    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    return (scope, target, prog)

def setup_cw(scope):
    scope.default_setup()
    scope.adc.offset = 0
    scope.gain.gain = 65
    scope.adc.samples = 24400
    
    # per docs has to be like that for DecodeIO and SAD
    scope.adc.basic_mode = "rising_edge"

def setup_basic(scope, offset, nr_samples):
    setup_cw(scope)

    scope.adc.basic_mode = "rising_edge"
    scope.trigger.module = "basic"
    scope.trigger.triggers = "tio4"

def reset_tio1():
    scope.io.tio1 = "gpio_low"
    sleep(0.1)
    scope.io.tio1 = "gpio_high"
    sleep(0.2)


def collect_trace(scope, ec_trigger=False):
    scope.io.tio1 = "gpio_low"
    if ec_trigger:
        scope.EC.reset(keep_config=True)

    scope.arm()
    
    # As long as only the A7's power port is connected to reset this will issue a 1us reset
    # The CW can trigger on the reset release
    chipfail_lib.manual_glitch(fpga)
    
    if ec_trigger:
        scope.EC.start()

    scope.io.tio1 = "gpio_high"
    scope.capture()
    return scope.get_last_trace()

def setup_ec(scope):
    setup_cw(scope)
    scope.EC.reset()
    scope.EC.window_size = 250
    scope.EC.decimate = 16
    scope.EC.threshold = 0.03
    scope.EC.hold_cycles = 200
    scope.EC.absolute_values = True
    scope.EC.edge_num = 1
    scope.EC.edge_type = "falling_edge"
    scope.EC.start()
    scope.trigger.module = "EC"

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

    # 50x downsampling: 300*50 = 15.000. 1 cycle = 34ns --> 510.000 ns = 510 us
    MIN_OFFSET = 12549870
    MAX_OFFSET = 12551700
    STEP_SIZES = [1]
    OFFSET_REPEAT = 10000
    
    MIN_WIDTH = 1361
    MAX_WIDTH = 1362
    
    WIDTH_STEPS = 20
    WIDTH_REPEAT = 0

    # scope, _, _ = load_bitstream("../../hardware/capture/chipwhisperer-lite/cwlite_interface_ec_256_downsampling.bit")
    scope, target, prog = Setup_Generic.setup(version=None, platform=PLATFORM)
    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB1", baudrate=115200)
    target = serial.Serial("/dev/ttyUSB2", baudrate=115200, timeout=0.2)

    offset = 0
    nr_samples = 24400
    
    setup_basic(scope, offset, nr_samples)
    # setup_ec(scope)
    setup_glitcher(scope)
    chipfail_lib.setup(fpga)
    scope.adc.decimate = 15
    # project = cw.create_project("projects/ram_traces")

    width_repeat = 0
    success_ctr = 0
    try_ctr = 1
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
    # widths = [1280, 1410, 1290, 1420, 1300, 1430, 1310, 1440, 1320, 1450, 1200, 1330, 1340, 1350, 1360, 1240, 1370, 1250, 1380, 1260, 1390, 1270, 1400]

    random.shuffle(widths)
    widths_iter = iter(widths)
    width = next(widths_iter)
    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, width)

    used_len = len(progress["used_offsets"])
    print(f"starting with progress len: {used_len}")

    try:
        while not success:
            # increase search resolution from time to time
            for step_size in STEP_SIZES:
                progress["step_size"] = step_size
                # only decrease step_size after repeating 20 times
                for i in range(0,OFFSET_REPEAT):
                    progress["cur_repeat"] = i

                    offsets = set(range(MIN_OFFSET, MAX_OFFSET, step_size))
                    new_offsets = list(offsets.difference(set(progress)))
                    # new_offsets = [784, 787, 788, 794, 804, 812, 812, 822, 842, 846, 850, 858, 859]
                    random.shuffle(new_offsets)

                    for offset in new_offsets:
                        time_pre = datetime.datetime.now()

                        width_repeat += 1
                        if width_repeat > WIDTH_REPEAT:
                            try:
                                width = next(widths_iter)
                            except StopIteration:
                                widths_iter = iter(widths)
                                width = next(widths_iter)

                            chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, width)
                            width_repeat = 0

                        chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_DELAY, offset)

                        wave = collect_trace(scope)
                        # project.traces.append(Trace(wave, None, None, None))
                        try_ctr += 1   
                        # plt.plot(wave)
                        # plt.show()
                        success, timeout, response = chipfail_lib.success_uart(target, offset, width)
                        # if timeout:
                        #     # chipfail_lib.flush_uart(target)
                        #     # reset_tio1()

                        if success:
                            print("success?")
                            success_ctr += 1
                        chipfail_lib.flush_uart(target)
                        
                        progress["used_widths"].append(width)
                        progress["used_offsets"].append(offset)
                        progress["responses"].append(base64.b64encode(response).decode())

                        # sleep(0.2)    
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
        print(f"--> success prob: {(success_ctr/try_ctr)*100}")
        # project.save()
        save_progress(progress_l)
        exit(0)
