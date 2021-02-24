import chipfail_lib
import serial
import Setup_Generic

from time import sleep
import datetime
import random
import matplotlib.pyplot as plt

PROGRESS_FILE = "progress.txt"

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
    #scope.adc.presamples = 400
    
    # per docs has to be like that for DecodeIO and SAD
    scope.adc.basic_mode = "rising_edge"

def setup_ec(scope):
    setup_cw(scope)
    scope.EC.reset()
    scope.EC.window_size = 200
    scope.EC.threshold = 0.015
    scope.EC.hold_cycles = 150
    scope.EC.absolute_values = True
    scope.EC.edge_num = 1
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
        lines = file.readlines()
        lines_stripped = [int(line.strip()) for line in lines]

    return lines_stripped

def save_progress(used_offsets):
    with open(PROGRESS_FILE, "w+") as file:
        file.truncate(0)
        strings = [str(offset) for offset in used_offsets]
        file.write("\n".join(strings))

if __name__ == "__main__":

    SCOPETYPE = 'OPENADC'
    PLATFORM = 'CWLITEXMEGA'
    CRYPTO_TARGET = 'AVRCRYPTOLIB'

    # Initialize connection to ARTY A7 FPGA
    fpga = serial.Serial("/dev/ttyUSB1", baudrate=115200)
    target = serial.Serial("/dev/ttyUSB2", baudrate=115200, timeout=0.2)

    scope, _, _ = load_bitstream("../../hardware/capture/chipwhisperer-lite/cwlite_interface_ec_256.bit")

    offset = 0
    nr_samples = 24400

    setup_ec(scope)
    setup_glitcher(scope)
    chipfail_lib.setup(fpga, delay=0, glitch_pulse=1)
    scope.adc.decimate = 50


    # 50x downsampling: 300*50 = 15.000. 1 cycle = 34ns --> 510.000 ns = 510 us
    MIN_OFFSET = 8364
    MAX_OFFSET = 284240
    OFFSET_STEP = 4
    MIN_WIDTH = 1160
    MAX_WIDTH = 1164
    WIDTH_STEP = 1
    
    success = False
    offsets = range(MIN_OFFSET, MAX_OFFSET)
    try:
        used_offsets = read_progress()
    except:
        with open(PROGRESS_FILE, "w"):
            pass
        used_offsets = []

    print(f"starting with used_offsets len: {len(used_offsets)}")

    try:
        while not success:
            for width in range(MIN_WIDTH, MAX_WIDTH, WIDTH_STEP):
                chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_GLITCH_PULSE, width)
                
                offsets = set(range(MIN_OFFSET, MAX_OFFSET+1))
                new_offsets = list(offsets.difference(set(used_offsets)))
                random.shuffle(new_offsets)

                for offset in new_offsets:
                    time_pre = datetime.datetime.now()
                    
                    chipfail_lib.cmd_uint32(fpga, chipfail_lib.CMD_SET_DELAY, offset)
                    collect_trace(scope)
                    success = chipfail_lib.success_uart(target, offset, width)
                    chipfail_lib.wait_until_rdy(fpga)
                        
                    used_offsets.append(offset)
                        
                    print(f"\tcurrent time/it: {datetime.datetime.now() - time_pre}")
                
                with open(PROGRESS_FILE, "w+") as file:
                    file.truncate(0)

                used_offsets = []
    except KeyboardInterrupt:
        save_progress(used_offsets)
