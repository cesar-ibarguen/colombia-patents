"""
Helpers for patents_analysis.ipynb: database connection and chart style.

Usage in the notebook:
    from helpers import q, new_ax, finish, BLUE, ORANGE, AQUA, INK_2

The MySQL password is never written here (the repository is public): it is read from the
environment variable MYSQL_PASSWORD, or asked for when the module is imported.
"""
import getpass
import os

import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import URL, create_engine, text

# ---------------------------------------------------------------- database connection
USER = "cesar"
HOST = "127.0.0.1"
DATABASE = "patents"
PASSWORD = os.environ.get("MYSQL_PASSWORD") or getpass.getpass("MySQL password: ")

# URL.create handles passwords with special characters (@, #, %, /, :) safely
engine = create_engine(URL.create("mysql+pymysql", username=USER, password=PASSWORD,
                                  host=HOST, port=3306, database=DATABASE))


def q(sql):
    """Run a SQL query and return the result as a pandas DataFrame."""
    return pd.read_sql(text(sql), engine)


# ---------------------------------------------------------------- chart style
# Colorblind-safe colors: BLUE for one series; BLUE, ORANGE, AQUA (in that order) for more.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SOURCE = "Source: SIC, patent applications 2000–2021"
IMAGES = "../images"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "font.size": 11,
})


def new_ax(figsize=(9, 4.8)):
    """Create a figure with one chart."""
    return plt.subplots(figsize=figsize)


def finish(fig, ax, title, xlabel="", ylabel="", filename=None):
    """Add title, labels and source; optionally save the chart to images/."""
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=INK, pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.text(0.01, 0.01, SOURCE, fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    if filename:
        os.makedirs(IMAGES, exist_ok=True)
        fig.savefig(f"{IMAGES}/{filename}", dpi=200)
    plt.show()
