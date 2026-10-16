from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[2]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def setup_plot():
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.facecolor':'#2E3440','axes.facecolor':'#2E3440',
        'text.color':'#ECEFF4','axes.labelcolor':'#ECEFF4','xtick.color':'#D8DEE9',
        'ytick.color':'#D8DEE9','axes.edgecolor':'#4C566A','grid.color':'#4C566A',
        'figure.figsize':(9,4),'figure.dpi':120,'savefig.facecolor':'#2E3440'})
    return plt


def record(*args, **kwargs):
    raise RuntimeError("Private run recording is not part of the public runtime")
