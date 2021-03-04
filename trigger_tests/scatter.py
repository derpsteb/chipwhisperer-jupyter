import json
import base64
import matplotlib.pyplot as plt

import pandas as pd
import numpy as np
import sys
import argparse

def build_scatter(progress):
    for i, name in enumerate(progress["responses"]):
        if name.startswith(b"000"):
            progress["responses"][i] = b"0..0 Locked"
        if name == b"":
            progress["responses"][i] = b" mute"
        if b"!!! Exception !!!" in name:
            progress["responses"][i] = b"[0000....] !!! Exception !!! [cpsr:0x???, lr:0x???, spsr:0x???]"
        if b"MB1-BIT() boot status" in name:
            progress["responses"][i] = b"[0000.0..] MB1-BIT() boot status dump :"
        if b"Last seen error" in name:
            progress["responses"][i] = b"[0000....] Last seen error : 0x00000000"
        if name.startswith(b"\xff\xff\xff\xff\xff\xff\xff\xff"):
            progress["responses"][i] = b"ff..ff"
        if type(name) == str:
            progress["responses"][i] = progress["responses"][i].encode()

    df = pd.DataFrame(progress)
    groups = df.groupby("responses")

    fig, ax = plt.subplots()

    for name, group in groups:
        if name.startswith(b"Locked"):
            continue

        ax.plot(np.array(group["used_offsets"]), np.array(group["used_widths"]), marker='o', linestyle='', label=name)

    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
    plt.show()

def transform(progress, outpath):
    with open(outpath, "wb") as file:
        file.writelines(progress["responses"])

def load_vanilla(data_file):
    with open(data_file, "r") as file:
        progress = json.loads(file.read())
        for i, resp in enumerate(progress["responses"]):
            progress["responses"][i] = base64.b64decode(resp)
    return progress

def load_pickled(data_file):
    import jsonpickle
    with open(data_file, "r") as file:
        progress = jsonpickle.decode(file.read())
    return progress

parser = argparse.ArgumentParser(description='Utility to handle glitching logs')
parser.add_argument('cmd', choices=['plot', 'transform'], action='store', type=str, help='what to do')
parser.add_argument('logfile', action='store', type=str, help='logfile to take data from')
parser.add_argument('--outfile', action='store', type=str, help='outfile to put data to')

# mutually exclusive -p/-v
bool_parser = parser.add_mutually_exclusive_group(required=False)
bool_parser.add_argument('-p', dest='pickled', action='store_true', help="jsonpickle was used for serialization")
bool_parser.add_argument('-v', dest='pickled', action='store_false', help="json+b64 was used for serialization")
parser.set_defaults(pickled=False)

args = parser.parse_args()

if args.pickled:
    progress = load_pickled(args.logfile)
else:
    progress = load_vanilla(args.logfile)

if args.cmd == "plot":
    build_scatter({"used_offsets": progress["used_offsets"][:15000], "used_widths": progress["used_widths"][:15000], "responses": progress["responses"][:15000]})
if args.cmd == "transform":
    if not args.outfile:
        print("Error, no outfile given for 'transform' cmd")
        exit(1)
    transform(progress)

# build_scatter({"used_offsets": progress["used_offsets"][25000:], "used_widths": progress["used_widths"][25000:], "responses": progress["responses"][25000:]})