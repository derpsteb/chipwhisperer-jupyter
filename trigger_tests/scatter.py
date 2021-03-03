import json
import matplotlib.pyplot as plt

import pandas as pd
import numpy
import sys

PROGRESS_FILE = sys.argv[1]

def build_scatter(progress):
    df = pd.DataFrame(progress)
    groups = df.groupby("responses")

    fig, ax = plt.subplots()
    for name, group in groups:
        if name == "":
            name = "mute"
        # if name.startswith("Locked"):
        #     continue
        
        ax.plot(numpy.array(group["used_offsets"]), numpy.array(group["used_widths"]), marker='o', linestyle='', label=name)

    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
    plt.show()

with open(PROGRESS_FILE, "r") as file:
    progress = json.loads(file.read())


build_scatter({"used_offsets": progress["used_offsets"][:25000], "used_widths": progress["used_widths"][:25000], "responses": progress["responses"][:25000]})
# build_scatter({"used_offsets": progress["used_offsets"][25000:], "used_widths": progress["used_widths"][25000:], "responses": progress["responses"][25000:]})