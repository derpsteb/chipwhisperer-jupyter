import json
import matplotlib.pyplot as plt

import pandas as pd
import numpy as np
import sys

PROGRESS_FILE = sys.argv[1]

def build_scatter(progress):
    for i, name in enumerate(progress["responses"]):
        if name.startswith("000"):
            progress["responses"][i] = "0..0 Locked"
        if name == "":
            progress["responses"][i] = " mute"
        if "!!! Exception !!!" in name:
            progress["responses"][i] = "[0000....] !!! Exception !!! [cpsr:0x???, lr:0x???, spsr:0x???]"
        if "MB1-BIT() boot status" in name:
            progress["responses"][i] = "[0000.0..] MB1-BIT() boot status dump :"
        if "Last seen error" in name:
            progress["responses"][i] = "[0000....] Last seen error : 0x00000000"

    df = pd.DataFrame(progress)
    groups = df.groupby("responses")

    fig, ax = plt.subplots()

    for name, group in groups:
        if name.startswith("Locked"):
            continue

        ax.plot(np.array(group["used_offsets"]), np.array(group["used_widths"]), marker='o', linestyle='', label=name)

    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
    plt.show()

with open(PROGRESS_FILE, "r") as file:
    progress = json.loads(file.read())


build_scatter({"used_offsets": progress["used_offsets"][:15000], "used_widths": progress["used_widths"][:15000], "responses": progress["responses"][:15000]})
# build_scatter({"used_offsets": progress["used_offsets"][25000:], "used_widths": progress["used_widths"][25000:], "responses": progress["responses"][25000:]})