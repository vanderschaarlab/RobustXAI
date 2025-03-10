import logging
import random
from pathlib import Path
from typing import List

import numpy as np
import torch
from networkx import Graph
from torch_geometric.data import Data as GraphData
from torch_geometric.utils import to_networkx


def set_random_seed(seed: int) -> None:
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)


def direct_sum(input_tensors):
    """
    Takes a list of tensors and stacks them into one tensor
    """
    unrolled = [tensor.flatten() for tensor in input_tensors]
    return torch.cat(unrolled)


def to_molecule(data: GraphData) -> Graph:
    ATOM_MAP = [
        "C",
        "O",
        "Cl",
        "H",
        "N",
        "F",
        "Br",
        "S",
        "P",
        "I",
        "Na",
        "K",
        "Li",
        "Ca",
    ]
    g = to_networkx(data, node_attrs=["x"], edge_attrs=["edge_attr"])
    for u, data in g.nodes(data=True):
        data["name"] = ATOM_MAP[data["x"].index(1.0)]
        del data["x"]
    for u, v, data in g.edges(data=True):
        data["valence"] = data["edge_attr"].index(1.0) + 1
        del data["edge_attr"]
    return g


def get_all_checkpoint_paths(checkpoint_dir: Path) -> List[Path]:
    """
    Returns the list of all checkpoints in the given directory
    """
    return list(checkpoint_dir.glob("*.ckpt"))


def get_best_checkpoint(checkpoint_dir: Path) -> Path:
    """
    Returns the path to the checkpoint with the highest validation accuracy
    """
    checkpoint_paths = get_all_checkpoint_paths(checkpoint_dir)
    accuracies = []
    for checkpoint_path in checkpoint_paths:
        # Find the validation accuracy in the string
        str_idx = checkpoint_path.name.find("val_acc=") + 8
        accuracies.append(float(checkpoint_path.name[str_idx : str_idx + 4]))
    best_checkpoint_idx = np.argmax(accuracies)
    logging.info(f"Loading best checkpoint: {checkpoint_paths[best_checkpoint_idx]}")
    return checkpoint_paths[best_checkpoint_idx]
