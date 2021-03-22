import serial
import struct
import datetime

CMD_TOGGLE_LED = 65
CMD_POWER_CYCLE = 66
CMD_SET_GLITCH_PULSE = 67 # uint32
CMD_SET_DELAY = 68 # uint32
CMD_SET_POWER_PULSE = 69 # uint32
CMD_GLITCH = 70
CMD_READ_GPIO = 71
CMD_ENABLE_GLITCH_POWER_CYCLE = 72 # bool/byte
CMD_GET_STATE = 73 # Get state of fpga
CMD_GET_FLANKS = 50 # Get current flank count
CMD_SET_EDGE_COUNTER = 74
CMD_SET_TRIGGER_MODE = 75
CMD_SET_TRIGGER_LENGTH = 76

def cmd_toggle_led(fpga):
    fpga.write(chr(CMD_TOGGLE_LED).encode("ASCII"))

def cmd(fpga, command):
    fpga.write(chr(command).encode("ASCII"))

def cmd_uint32(fpga, command, u32):
    fpga.write(chr(command).encode("ASCII"))
    data = struct.pack(">L", u32)
    fpga.write(data)

def cmd_uint8(fpga, command, u8):
    fpga.write(chr(command).encode("ASCII"))
    data = struct.pack("B", u8)
    fpga.write(data)

def cmd_read_uint8(fpga, command):
    fpga.write(chr(command).encode("ASCII"))
    return fpga.read(1)[0]

def cmd_read_uint32(fpga, command):
    fpga.write(chr(command).encode("ASCII"))
    return fpga.read(4)

def setup(fpga, power_cycle_pulse=30, delay=0, glitch_pulse=10, edge_counter=1, trigger_length=1, power_cycle_before_glitch=0, trigger_mode=0):
    # 1 == 10ns
    cmd_uint32(fpga, CMD_SET_POWER_PULSE, power_cycle_pulse)
    cmd_uint32(fpga, CMD_SET_DELAY, delay)
    cmd_uint32(fpga, CMD_SET_GLITCH_PULSE, glitch_pulse)
    cmd_uint32(fpga, CMD_SET_EDGE_COUNTER, edge_counter)
    cmd_uint32(fpga, CMD_SET_TRIGGER_LENGTH, trigger_length)
    cmd_uint8(fpga, CMD_ENABLE_GLITCH_POWER_CYCLE, power_cycle_before_glitch)
    cmd_uint8(fpga, CMD_SET_TRIGGER_MODE, trigger_mode)

def manual_glitch(fpga):
    cmd(fpga, CMD_GLITCH)
    
def wait_until_rdy(fpga):
    # Loop until the status is == 0, aka the glitch is done.
    # This avoids having to manually time the glitch :)
    while(cmd_read_uint8(fpga, CMD_GET_STATE)):
        pass

def flush_uart(ser):
    ser.flushInput()
    ser.flushOutput()

def success_uart(target, offset, pulse, expected_reponse=b'Open\r\n', dump=True):
    response = target.read(36)
    timeout = False
    if len(response) != 36:
        timeout = True
    # response = target.read(38)
    print(f"time: {datetime.datetime.now().time()} | offset: {offset} | pulse: {pulse} | response: {response}", flush=True)
    # if not b"!100 - 100 - 10000\n" in response:
    # if response != b'\x00\nstarting:\n1000000 \xe2\x88\x92 1000 \xe2\x88\x92 1000\n':
    # if response != b'!100 - 100 - 10000\n':
    if response == b"Open | BPMP_ATCMCFG_SB_CFG_0: 0x3\n":
        print("*** SUCCESS ***", flush=True)
        if dump:
            target.timeout = None
            hexdump = target.read(1024*96)
            with open("./hexdump.txt", "w") as file:
                file.write(hexdump.decode())
        return (True, timeout, response)
    elif response == b"SecureBoot? | BPMP_ATCMCFG_SB_CFG_0: 0x1\n":
        print("Got into SecureBoot?!", flush=True)
        response = target.readline()
        return (True, timeout, response)
    elif response == b"APB2JTAG? | BPMP_ATCMCFG_SB_CFG_0: 0x0\n"
        print("Enabled JTAG?", flush=True)
        response = target.readline()
        print(f"reponse: {response}", flush=True)
        response = target.readline()
        print(f"reponse: {response}", flush=True)
        response = target.readline()
        print(f"reponse: {response}", flush=True)
        return (True, timeout, response)
    else:
        return (False, timeout, response)

def success_skip_sig_check(target, offset, pulse):
    response = target.read(36)

    print(f"time: {datetime.datetime.now().time()} | offset: {offset} | pulse: {pulse} | response: {response}", flush=True)
    if len(response) > 0:
        print("*** SUCCESS ***", flush=True)
        return (True, response)
    else:
        return (False, b"")