import chipfail_lib
import serial
import Setup_Generic

import json
from time import sleep
import datetime
import random
import matplotlib.pyplot as plt
import sys
import base64
import edge_counter


PROGRESS_FILE = "progress.txt"
cur_time = datetime.datetime.now()
LOG_FILE = f"{cur_time.strftime('%d%m%y_%X')}.log"

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
    scope.gain.gain = 50
    scope.adc.samples = 24400
    
    # per docs has to be like that for DecodeIO and SAD
    scope.adc.basic_mode = "rising_edge"

def setup_ec(scope):
    setup_cw(scope)
    scope.EC.reset()
    scope.EC.window_size = 250
    scope.EC.decimate = 1
    scope.EC.threshold = 0.015
    scope.EC.hold_cycles = 200
    scope.EC.absolute_values = True
    scope.EC.edge_num = 2
    scope.EC.edge_type = "falling_edge"
    scope.EC.start()
    scope.trigger.module = "EC"

def collect_trace(scope):
    scope.io.tio1 = "gpio_low"
    scope.EC.reset(keep_config=True)
    scope.arm()
    
    # The actual glitch signal is produced by the A7
    # CW is used to control the target and trigger A7
    chipfail_lib.manual_glitch(fpga)

    scope.EC.start()
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
    
def reset_tio1():
    scope.io.tio1 = "gpio_low"
    sleep(0.1)
    scope.io.tio1 = "gpio_high"
    sleep(0.2)

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
        file.write(json.dumps([log], ensure_ascii=False).encode())

if __name__ == "__main__":

    SCOPETYPE = 'OPENADC'
    PLATFORM = 'CWLITEXMEGA'
    CRYPTO_TARGET = 'AVRCRYPTOLIB'

    MIN_OFFSET = 100000
    MAX_OFFSET = 175880
    STEP_SIZES = [20]
    OFFSET_REPEAT = 20000

    WIDTH = 1329
    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB1", baudrate=115200)
    target = serial.Serial("/dev/ttyUSB2", baudrate=115200, timeout=0.2)

    scope, _, _ = load_bitstream("../../hardware/capture/chipwhisperer-lite/cwlite_interface_ec_256.bit")

    offset = 0
    nr_samples = 24400

    setup_ec(scope)
    setup_glitcher(scope)
    scope.adc.decimate = 10
    chipfail_lib.setup(fpga, delay=0, glitch_pulse=1)
    edge_c = edge_counter.edge_count(250, 0.01, None, "falling_edge", 150, decimate=16)

    # 50x downsampling: 300*50 = 15.000. 1 cycle = 34ns --> 510.000 ns = 510 us
    
    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, WIDTH)
    success = False
    offsets = range(MIN_OFFSET, MAX_OFFSET)
    log = {"used_offsets": [], "used_widths": [], "responses": []}
    try:
        progress = read_progress()
    except:
        with open(PROGRESS_FILE, "w"):
            pass
        progress = {"step_size": 0, "cur_repeat": 0, "used_offsets": []}

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
                random.shuffle(new_offsets)

                for offset in new_offsets:
                    time_pre = datetime.datetime.now()
                    
                    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_DELAY, offset)
                    trace = collect_trace(scope)

                    # plt.plot(trace)
                    # plt.show()
                    # convol, triggers = edge_c.run(trace, interpolation="avg")

                    # print(triggers)
                    # plt.plot(convol)
                    # plt.show()
                    
                    # import code
                    # variables = {**globals(), **locals()}
                    # shell = code.InteractiveConsole(variables)
                    # shell.interact()

                    success, timeout, response = chipfail_lib.success_uart(target, offset, WIDTH, b'Open\r\n', False)
                    # success, response = chipfail_lib.success_skip_sig_check(target, offset, WIDTH)
                    chipfail_lib.flush_uart(target)
                    if success:
                        exit(0)
                    chipfail_lib.flush_uart(target)
                    # reset_tio1()
                    # chipfail_lib.wait_until_rdy(fpga)
                        
                    progress["used_offsets"].append(offset)

                    log["used_widths"].append(WIDTH)
                    log["used_offsets"].append(offset)
                    log["responses"].append(base64.b64encode(response).decode())

                    sleep(0.2)    
                    print(f"\tcurrent time/it: {datetime.datetime.now() - time_pre}")


                # Remove any leftover progress from FS
                with open(PROGRESS_FILE, "w+") as file:
                    file.truncate(0)
                progress["used_offsets"] = []

    # except Exception:
    #     print("unknown exception:")
    #     print(traceback.format_exc())
    finally:
        save_progress(progress)
        save_log(log)
