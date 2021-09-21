import ipyvuetify as v
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import panel as pn
from IPython.core.display import HTML, display
from IPython.display import Javascript
from ipywidgets import Button, Checkbox, HBox, Image, Layout, Output, VBox
from krakow import krakow
from krakow.utils import normalized_dasgupta_cost, split_into_n_children
from scipy.cluster.hierarchy import cut_tree, leaves_list, to_tree

pn.extension()

from yourtube.material_components import (
    MaterialButton,
    MaterialSwitch,
    required_modules,
)

mb = MaterialButton(width=800, height=50)
row = pn.Row(mb, required_modules)
pn.panel(row).servable()
