import argparse
import itertools
import json
import logging
import textwrap
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import seaborn as sns

sns.set_style("whitegrid")
sns.set_palette("colorblind")
markers = {
    "DeepLift": "o",
    "Feature Ablation": "s",
    "Feature Occlusion": "X",
    "Feature Permutation": "D",
    "Gradient Shap": "v",
    "Integrated Gradients": "p",
    "Influence Functions": "^",
    "Rep. Similar-Lin1": "*",
    "SimplEx-Lin1": "H",
    "TracIn": ">",
    "CAR-Lin1": "<",
    "CAV-Lin1": "d",
}


def single_robustness_plots(plot_dir: Path, dataset: str, experiment_name: str) -> None:
    metrics_df = pd.read_csv(plot_dir / "metrics.csv")
    for model_type in metrics_df["Model Type"].unique():
        sub_df = metrics_df[metrics_df["Model Type"] == model_type]
        y = (
            "Explanation Equivariance"
            if "Explanation Equivariance" in metrics_df.columns
            else "Explanation Invariance"
        )
        ax = sns.boxplot(sub_df, x="Explanation", y=y, showfliers=False)
        wrap_labels(ax, 10)
        plt.ylim(-1.1, 1.1)
        plt.tight_layout()
        plt.savefig(
            plot_dir
            / f'{experiment_name}_{dataset}_{model_type.lower().replace(" ", "_")}.pdf'
        )
        plt.close()


def global_robustness_plots(experiment_name: str) -> None:
    sns.set(font_scale=0.9)
    sns.set_style("whitegrid")
    sns.set_palette("colorblind")
    with open(Path.cwd() / "results_dir.json") as f:
        path_dic = json.load(f)
    global_df = []
    for dataset in path_dic:
        dataset_df = pd.read_csv(
            Path.cwd() / path_dic[dataset] / experiment_name / "metrics.csv"
        )
        dataset_df["Dataset"] = [dataset] * len(dataset_df)
        global_df.append(dataset_df)
    global_df = pd.concat(global_df)
    rename_dic = {
        "SimplEx-Lin1": "SimplEx-Inv",
        "SimplEx-Conv3": "SimplEx-Equiv",
        "Representation Similarity-Lin1": "Rep. Similar-Inv",
        "Representation Similarity-Conv3": "Rep. Similar-Equiv",
        "CAR-Lin1": "CAR-Inv",
        "CAR-Conv3": "CAR-Equiv",
        "CAV-Lin1": "CAV-Inv",
        "CAV-Conv3": "CAV-Equiv",
        "SimplEx-Phi": "SimplEx-Equiv",
        "SimplEx-Rho": "SimplEx-Inv",
        "Representation Similarity-Phi": "Rep. Similar-Equiv",
        "Representation Similarity-Rho": "Rep. Similar-Inv",
        "CAR-Phi": "CAR-Equiv",
        "CAR-Rho": "CAR-Inv",
        "CAV-Phi": "CAV-Equiv",
        "CAV-Rho": "CAV-Inv",
        "CAR-Conv1": "CAR-Equiv",
        "CAV-Conv1": "CAV-Equiv",
        "SimplEx-Conv1": "SimplEx-Equiv",
        "Representation Similarity-Conv1": "Rep. Similar-Equiv",
        "CAR-Layer3": "CAR-Inv",
        "CAV-Layer3": "CAV-Inv",
        "SimplEx-Layer3": "SimplEx-Inv",
        "Representation Similarity-Layer3": "Rep. Similar-Inv",
        "CAR-Embedding": "CAR-Inv",
        "CAV-Embedding": "CAV-Inv",
        "SimplEx-Embedding": "SimplEx-Inv",
        "Representation Similarity-Embedding": "Rep. Similar-Inv",
    }
    global_df = global_df.replace(rename_dic)
    global_df = global_df[
        (global_df["Model Type"] == "All-CNN")
        | (global_df["Model Type"] == "GNN")
        | (global_df["Model Type"] == "Deep-Set")
        | (global_df["Model Type"] == "D8-Wide-ResNet")
        | (global_df["Model Type"] == "bow_classifier")
    ]
    y = (
        "Explanation Equivariance"
        if "Explanation Equivariance" in global_df.columns
        else "Explanation Invariance"
    )
    ax = sns.boxplot(global_df, x="Dataset", hue="Explanation", y=y, showfliers=False)
    wrap_labels(ax, 10)
    plt.ylim(-1.1, 1.1)
    box_patches = [
        patch for patch in ax.patches if type(patch) == matplotlib.patches.PathPatch
    ]
    if (
        len(box_patches) == 0
    ):  # in matplotlib older than 3.5, the boxes are stored in ax2.artists
        box_patches = ax.artists
    num_patches = len(box_patches)
    lines_per_boxplot = len(ax.lines) // num_patches
    for i, patch in enumerate(box_patches):
        # Set the linecolor on the patch to the facecolor, and set the facecolor to None
        col = patch.get_facecolor()
        patch.set_edgecolor(col)
        patch.set_facecolor("None")

        # Each box has associated Line2D objects (to make the whiskers, fliers, etc.)
        # Loop over them here, and use the same color as above
        for line in ax.lines[i * lines_per_boxplot : (i + 1) * lines_per_boxplot]:
            line.set_color(col)
            line.set_mfc(col)  # facecolor of fliers
            line.set_mec(col)  # edgecolor of fliers

    # Also fix the legend
    for legpatch in ax.legend_.get_patches():
        col = legpatch.get_facecolor()
        legpatch.set_edgecolor(col)
        legpatch.set_facecolor("None")
    sns.despine(left=True)
    plt.tight_layout()
    plt.savefig(Path.cwd() / f"results/{experiment_name}_global_robustness.pdf")
    plt.close()


def relaxing_invariance_plots(
    plot_dir: Path, dataset: str, experiment_name: str
) -> None:
    sns.set(font_scale=1.2)
    sns.set_style("whitegrid")
    sns.set_palette("colorblind")
    metrics_df = pd.read_csv(plot_dir / "metrics.csv")
    metrics_df = metrics_df.drop(
        metrics_df[
            (metrics_df.Explanation == "SimplEx-Conv3")
            | (metrics_df.Explanation == "Representation Similarity-Conv3")
            | (metrics_df.Explanation == "CAR-Conv3")
            | (metrics_df.Explanation == "CAV-Conv3")
        ].index
    )
    rename_dic = {"Representation Similarity-Lin1": "Rep. Similar-Lin1"}
    metrics_df = metrics_df.replace(rename_dic)
    y = (
        "Explanation Equivariance"
        if "Explanation Equivariance" in metrics_df.columns
        else "Explanation Invariance"
    )
    plot_df = metrics_df.groupby(["Model Type", "Explanation"]).mean()
    plot_df[["Model Invariance CI", f"{y} CI"]] = (
        2 * metrics_df.groupby(["Model Type", "Explanation"]).sem()
    )
    sns.scatterplot(
        plot_df,
        x="Model Invariance",
        y=y,
        hue="Model Type",
        edgecolor="black",
        alpha=0.5,
        style="Explanation",
        markers=markers,
        # markers=markers[: metrics_df["Explanation"].nunique()],
        s=100,
    )
    plt.errorbar(
        x=plot_df["Model Invariance"],
        y=plot_df[y],
        xerr=plot_df["Model Invariance CI"],
        yerr=plot_df[f"{y} CI"],
        ecolor="black",
        elinewidth=1.7,
        linestyle="",
        capsize=1.7,
        capthick=1.7,
    )
    plt.xscale("linear")
    plt.axline((0, 0), slope=1, color="gray", linestyle="dotted")
    plt.xlim(0, 1.1)
    plt.ylim(0, 1.1)
    plt.tight_layout()
    plt.savefig(plot_dir / f"{experiment_name}_{dataset}_relaxing_invariance.pdf")
    plt.close()


def mc_convergence_plot(plot_dir: Path, dataset: str, experiment_name: str) -> None:
    metrics_df = pd.read_csv(plot_dir / "metrics.csv")
    for estimator_name in metrics_df["Estimator Name"].unique():
        metrics_subdf = metrics_df[metrics_df["Estimator Name"] == estimator_name]
        x = metrics_subdf["Number of MC Samples"]
        y = metrics_subdf["Estimator Value"]
        ci = 2 * metrics_subdf["Estimator SEM"]
        plt.plot(x, y, label=estimator_name)
        plt.fill_between(x, y - ci, y + ci, alpha=0.2)
    plt.legend()
    plt.xlabel(r"$N_{\mathrm{samp}}$")
    plt.ylabel("Monte Carlo Estimator")
    plt.ylim(-1, 1)
    plt.tight_layout()
    plt.savefig(plot_dir / f"{experiment_name}_{dataset}.pdf")
    plt.close()


def understanding_randomness_plots(plot_dir: Path, dataset: str) -> None:
    data_df = pd.read_csv(plot_dir / "data.csv")
    sub_df = data_df[data_df["Baseline"] is False]
    print(sub_df)
    sns.kdeplot(data=data_df, x="y1", y="y2", hue="Model Type", fill=True)
    for model_type in data_df["Model Type"].unique():
        baseline = data_df[
            (data_df["Model Type"] == model_type) & (data_df["Baseline"] is True)
        ]
        plt.plot(
            baseline["y1"],
            baseline["y2"],
            marker="x",
            linewidth=0,
            label=f"Baseline {model_type}",
        )
    plt.axhline(0, color="black")
    plt.axvline(0, color="black")
    plt.xlabel(r"$y_1$")
    plt.ylabel(r"$y_2$")
    plt.legend()
    plt.show()


def enforce_invariance_plot(plot_dir: Path, dataset: str) -> None:
    sns.set(font_scale=1.3)
    sns.set_style("whitegrid")
    sns.set_palette("colorblind")
    metrics_df = pd.read_csv(plot_dir / "metrics.csv")
    sns.lineplot(metrics_df, x="N_inv", y="Explanation Invariance", hue="Explanation")
    plt.legend()
    plt.xlabel(r"$N_{\mathrm{inv}}$")
    plt.tight_layout()
    plt.savefig(plot_dir / f"enforce_invariance_{dataset}.pdf")
    plt.close()


def sensitivity_plot(plot_dir: Path, dataset: str) -> None:
    metrics_df = pd.read_csv(plot_dir / "metrics.csv")
    sns.scatterplot(
        metrics_df,
        x="Explanation Sensitivity",
        y="Explanation Equivariance",
        hue="Explanation",
        alpha=0.5,
        s=10,
    )
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_dir / f"sensitivity_comparison_{dataset}.pdf")
    plt.close()


def draw_molecule(g, edge_mask=None, draw_edge_labels=False):
    g = g.copy().to_undirected()
    node_labels = {}
    for u, data in g.nodes(data=True):
        node_labels[u] = data["name"]
    pos = nx.planar_layout(g)
    pos = nx.spring_layout(g, pos=pos)
    if edge_mask is None:
        edge_color = "black"
        widths = None
    else:
        edge_color = [edge_mask[(u, v)] for u, v in g.edges()]
        widths = [x * 10 for x in edge_color]
    nx.draw(
        g,
        pos=pos,
        labels=node_labels,
        width=widths,
        edge_color=edge_color,
        edge_cmap=plt.cm.Blues,
        node_color="azure",
    )

    if draw_edge_labels and edge_mask is not None:
        edge_labels = {k: ("%.2f" % v) for k, v in edge_mask.items()}
        nx.draw_networkx_edge_labels(g, pos, edge_labels=edge_labels, font_color="red")
    plt.show()


def wrap_labels(ax, width, break_long_words=False, do_y: bool = False) -> None:
    """
    Break labels in several lines in a figure
    Args:
        ax: figure axes
        width: maximal number of characters per line
        break_long_words: if True, allow breaks in the middle of a word
        do_y: if True, apply the function to the y axis as well
    Returns:
    """
    labels = []
    for label in ax.get_xticklabels():
        text = label.get_text()
        labels.append(
            textwrap.fill(text, width=width, break_long_words=break_long_words)
        )
    ax.set_xticklabels(labels, rotation=0)
    if do_y:
        labels = []
        for label in ax.get_yticklabels():
            text = label.get_text()
            labels.append(
                textwrap.fill(text, width=width, break_long_words=break_long_words)
            )
        ax.set_yticklabels(labels, rotation=0)


def global_relax_invariance() -> None:
    sns.set(font_scale=1.2)
    sns.set_style("whitegrid")
    with open(Path.cwd() / "results_dir.json") as f:
        path_dic = json.load(f)
    global_df = []
    for dataset, experiment_name in itertools.product(
        ["ECG", "Fa.MNIST"],
        ["feature_importance", "example_importance", "concept_importance"],
    ):
        dataset_df = pd.read_csv(
            Path.cwd() / path_dic[dataset] / experiment_name / "metrics.csv"
        )
        dataset_df["Dataset"] = [dataset] * len(dataset_df)
        dataset_df["Experiment"] = [experiment_name] * len(dataset_df)
        dataset_df = dataset_df.drop(
            dataset_df[
                (dataset_df.Explanation == "SimplEx-Conv3")
                | (dataset_df.Explanation == "Representation Similarity-Conv3")
                | (dataset_df.Explanation == "CAR-Conv3")
                | (dataset_df.Explanation == "CAV-Conv3")
            ].index
        )
        rename_dic = {"Representation Similarity-Lin1": "Rep. Similar-Lin1"}
        dataset_df = dataset_df.replace(rename_dic)
        global_df.append(dataset_df)
    global_df = pd.concat(global_df)

    n_datasets = len(global_df["Dataset"].unique())

    # Create a grid of plots
    fig, axs = plt.subplots(nrows=n_datasets, ncols=3, figsize=(17, 9), sharex=True)

    datasets = global_df["Dataset"].unique()
    y_titles = [
        "Feature Importance Equivariance",
        "Example Importance Invariance",
        "Concept Importance Invariance",
    ]
    experiments = global_df["Experiment"].unique()
    style_handles = []
    style_labels = []
    # Loop over the subplots and plot the data
    for i, dataset in enumerate(datasets):  # rows
        for j, experiment in enumerate(experiments):  # columns
            ax = axs[i, j]
            metrics_df = global_df[
                (global_df["Dataset"] == dataset)
                & (global_df["Experiment"] == experiment)
            ]
            y = (
                "Explanation Equivariance"
                if "feature" in experiment
                else "Explanation Invariance"
            )
            plot_df = metrics_df.groupby(["Model Type", "Explanation"]).mean(
                numeric_only=True
            )
            plot_df[["Model Invariance CI", f"{y} CI"]] = 2 * metrics_df.groupby(
                ["Model Type", "Explanation"]
            )[["Model Invariance", y]].apply("sem")
            sns.scatterplot(
                ax=ax,
                data=plot_df,
                x="Model Invariance",
                y=y,
                hue="Model Type",
                edgecolor="black",
                alpha=0.5,
                style="Explanation",
                markers=markers,
                s=200,
            )
            ax.errorbar(
                x=plot_df["Model Invariance"],
                y=plot_df[y],
                xerr=plot_df["Model Invariance CI"],
                yerr=plot_df[f"{y} CI"],
                ecolor="black",
                elinewidth=1.7,
                linestyle="",
                capsize=1.7,
                capthick=1.7,
            )
            ax.set_xscale("linear")
            ax.axline((0, 0), slope=1, color="gray", linestyle="dotted")
            ax.set_xlim(0, 1.1)
            ax.set_ylim(0, 1.1)
            ax.set_ylabel(y_titles[j])
            # Get handles and labels for hue and style legends
            handles, labels = ax.get_legend_handles_labels()
            explanation_cut = labels.index("Explanation") + int(j > 0)
            # Create separate legends for hue and style
            if i == 0 and j == 0:
                hue_handles = handles[
                    :explanation_cut
                ]  # first half of handles are for hue
                hue_labels = labels[:explanation_cut]
            if i == len(datasets) - 1:
                style_handles.extend(handles[explanation_cut:])
                style_labels.extend(labels[explanation_cut:])

            ax.legend().remove()
            if j == 1:
                ax.set_title(dataset)
    fig.legend(
        hue_handles + style_handles,
        hue_labels + style_labels,
        loc="lower center",
        ncol=5,
        bbox_to_anchor=(0.5, -0.1),
    )
    # fig.tight_layout()

    plt.savefig(Path.cwd() / "results/global_relax_invariance.pdf", bbox_inches="tight")
    plt.close()


def training_dynamic_plot(
    data_path: Path = Path.cwd() / "results/d8-wideresnet-training_dynamics.csv",
) -> None:
    sns.set(font_scale=1.0)
    sns.set_style("whitegrid")
    df = pd.read_csv(data_path)
    df = df[
        [
            "epoch",
            "cifar100_d8_wideresnet_seed42 - model_invariance",
            "stl10_d8_wideresnet_seed42 - model_invariance",
            "cifar100_d8_wideresnet_seed42 - gradient_equivariance",
            "stl10_d8_wideresnet_seed42 - gradient_equivariance",
        ]
    ]
    rename_cols = {
        "epoch": "Epoch",
        "cifar100_d8_wideresnet_seed42 - model_invariance": "CIFAR100 Model Invariance",
        "stl10_d8_wideresnet_seed42 - model_invariance": "STL10 Model Invariance",
        "cifar100_d8_wideresnet_seed42 - gradient_equivariance": "CIFAR100 Gradient Equivariance",
        "stl10_d8_wideresnet_seed42 - gradient_equivariance": "STL10 Gradient Equivariance",
    }
    df = df.rename(columns=rename_cols)
    data = []
    for dataset in ["CIFAR100", "STL10"]:
        for property in ["Model Invariance", "Gradient Equivariance"]:
            for epoch, score in df[["Epoch", f"{dataset} {property}"]].values:
                data.append(
                    {
                        "Dataset": dataset,
                        "Property": property,
                        "Epoch": epoch,
                        "Score": score,
                    }
                )

    plot_df = pd.DataFrame(data)
    sns.lineplot(data=plot_df, x="Epoch", y="Score", hue="Dataset", style="Property")
    plt.savefig(Path.cwd() / "results/training_dynamics.pdf", bbox_inches="tight")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment_name", type=str, default="feature_importance")
    parser.add_argument("--plot_name", type=str, default="relax_invariance")
    parser.add_argument("--dataset", type=str, default="ecg")
    parser.add_argument("--model", type=str, default="cnn32_seed42")
    parser.add_argument("--concept", type=str, default=None)
    args = parser.parse_args()
    with open(Path.cwd() / "results_dir.json") as f:
        path_dic = json.load(f)
    dataset_full_names = {
        "ecg": "ECG",
        "mut": "Muta.",
        "mnet": "M.Net40",
        "fashion_mnist": "Fa.MNIST",
    }
    plot_path = (
        (Path.cwd() / path_dic[dataset_full_names[args.dataset]] / args.experiment_name)
        if "global" not in args.plot_name and args.plot_name != "training_dynamics"
        else Path.cwd() / "results"
    )

    logging.info(f"Saving {args.plot_name} plot in {str(plot_path)}")
    match args.plot_name:
        case "robustness":
            single_robustness_plots(plot_path, args.dataset, args.experiment_name)
        case "global_robustness":
            global_robustness_plots(args.experiment_name)
        case "relax_invariance":
            relaxing_invariance_plots(plot_path, args.dataset, args.experiment_name)
        case "mc_convergence":
            mc_convergence_plot(plot_path, args.dataset, args.experiment_name)
        case "enforce_invariance":
            enforce_invariance_plot(plot_path, args.dataset)
        case "sensitivity_comparison":
            sensitivity_plot(plot_path, args.dataset)
        case "global_relax_invariance":
            global_relax_invariance()
        case "training_dynamics":
            training_dynamic_plot()
        case other:
            raise ValueError("Unknown plot name")
