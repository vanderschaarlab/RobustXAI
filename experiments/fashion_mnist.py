import argparse
import itertools
import logging
import os
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from captum.attr import (DeepLift, FeatureAblation, FeaturePermutation,
                         GradientShap, IntegratedGradients, Occlusion)
from torch.utils.data import DataLoader, RandomSampler, Subset

from datasets.loaders import FashionMnistDataset
from interpretability.concept import CAR, CAV, ConceptExplainer
from interpretability.example import (InfluenceFunctions,
                                      RepresentationSimilarity, SimplEx,
                                      TracIn)
from interpretability.feature import FeatureImportance
from interpretability.robustness import (InvariantExplainer, accuracy,
                                         explanation_equivariance_exact,
                                         explanation_invariance_exact,
                                         model_invariance_exact)
from models.images import AllCNN, StandardCNN
from utils.misc import set_random_seed
from utils.plots import (enforce_invariance_plot, relaxing_invariance_plots,
                         single_robustness_plots)
from utils.symmetries import AnchoredTranslation2D, Translation2D


def train_fashion_mnist_model(
    random_seed: int,
    latent_dim: int,
    batch_size: int,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / "results/fashion_mnist/",
    data_dir: Path = Path.cwd() / "datasets/fashion_mnist",
    max_displacement: int = 10,
) -> None:
    logging.info("Fitting the Fashion-Mnist classifiers")
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    set_random_seed(random_seed)
    model_dir = model_dir / model_name
    if not model_dir.exists():
        os.makedirs(model_dir)

    train_set = FashionMnistDataset(
        data_dir, train=True, max_displacement=max_displacement
    )
    test_set = FashionMnistDataset(
        data_dir, train=False, max_displacement=max_displacement
    )
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_set, batch_size=batch_size)
    models = {
        "Augmented-CNN": StandardCNN(latent_dim, f"{model_name}_augmented"),
        "All-CNN": AllCNN(latent_dim, f"{model_name}_allcnn"),
        "Standard-CNN": StandardCNN(latent_dim, f"{model_name}_standard"),
    }
    for model_type in models:
        logging.info(f"Now fitting a {model_type} classifier")
        if model_type == "Augmented-CNN":
            models[model_type].fit(
                device,
                train_loader,
                test_loader,
                model_dir,
                augmentation=True,
                checkpoint_interval=20,
                patience=50,
                n_epoch=500,
            )
        else:
            models[model_type].fit(
                device,
                train_loader,
                test_loader,
                model_dir,
                augmentation=False,
                checkpoint_interval=20,
                patience=50,
                n_epoch=500,
            )


def feature_importance(
    random_seed: int,
    latent_dim: int,
    plot: bool,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / "results/fashion_mnist/",
    data_dir: Path = Path.cwd() / "datasets/fashion_mnist",
    max_displacement: int = 10,
    n_test: int = 500,
    batch_size: int = 100,
) -> None:
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    set_random_seed(random_seed)
    test_set = FashionMnistDataset(
        data_dir, train=False, max_displacement=max_displacement
    )
    small_test_set = Subset(test_set, torch.randperm(len(test_set))[:n_test])
    test_loader = DataLoader(small_test_set, batch_size=batch_size, shuffle=False)
    model_dir = model_dir / model_name
    models = {
        "All-CNN": AllCNN(latent_dim, f"{model_name}_allcnn"),
        "Standard-CNN": StandardCNN(latent_dim, f"{model_name}_standard"),
        "Augmented-CNN": StandardCNN(latent_dim, f"{model_name}_augmented"),
    }
    attr_methods = {
        "DeepLift": DeepLift,
        "Integrated Gradients": IntegratedGradients,
        "Gradient Shap": GradientShap,
        "Feature Permutation": FeaturePermutation,
        "Feature Ablation": FeatureAblation,
        "Feature Occlusion": Occlusion,
    }
    save_dir = model_dir / "feature_importance"
    if not save_dir.exists():
        os.makedirs(save_dir)
    translation = Translation2D(max_displacement=max_displacement)
    metrics = []
    for model_type in models:
        logging.info(f"Now working with {model_type} classifier")
        model = models[model_type]
        model.load_metadata(model_dir)
        model.load_state_dict(torch.load(model_dir / f"{model.name}.pt"), strict=False)
        model.to(device).eval()
        model_inv = model_invariance_exact(model, translation, test_loader, device)
        logging.info(f"Model invariance: {torch.mean(model_inv).item():.3g}")
        for attr_name in attr_methods:
            logging.info(f"Now working with {attr_name}")
            feat_importance = FeatureImportance(attr_methods[attr_name](model))
            explanation_equiv = explanation_equivariance_exact(
                feat_importance, translation, test_loader, device
            )
            logging.info(
                f"Explanation equivariance: {torch.mean(explanation_equiv):.3g}"
            )
            for inv, equiv in zip(model_inv, explanation_equiv):
                metrics.append([model_type, attr_name, inv.item(), equiv.item()])
        metrics_df = pd.DataFrame(
            data=metrics,
            columns=[
                "Model Type",
                "Explanation",
                "Model Invariance",
                "Explanation Equivariance",
            ],
        )
    metrics_df.to_csv(save_dir / "metrics.csv", index=False)
    if plot:
        single_robustness_plots(save_dir, "fashion_mnist", "feature_importance")


def example_importance(
    random_seed: int,
    latent_dim: int,
    batch_size: int,
    plot: bool,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / "results/fashion_mnist/",
    data_dir: Path = Path.cwd() / "datasets/fashion_mnist",
    n_test: int = 1000,
    n_train: int = 100,
    recursion_depth: int = 100,
    max_displacement: int = 10,
) -> None:
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    set_random_seed(random_seed)
    train_set = FashionMnistDataset(
        data_dir, train=True, max_displacement=max_displacement
    )
    train_loader = DataLoader(train_set, n_train, shuffle=True)
    X_train, Y_train = next(iter(train_loader))
    X_train, Y_train = X_train.to(device), Y_train.to(device)
    train_sampler = RandomSampler(
        train_set, replacement=True, num_samples=recursion_depth * batch_size
    )
    train_loader_replacement = DataLoader(train_set, batch_size, sampler=train_sampler)
    test_set = FashionMnistDataset(
        data_dir, train=False, max_displacement=max_displacement
    )
    test_subset = Subset(test_set, torch.randperm(len(test_set))[:n_test])
    test_loader = DataLoader(test_subset, batch_size)
    models = {
        "All-CNN": AllCNN(latent_dim, f"{model_name}_allcnn"),
        "Standard-CNN": StandardCNN(latent_dim, f"{model_name}_standard"),
        "Augmented-CNN": StandardCNN(latent_dim, f"{model_name}_augmented"),
    }
    attr_methods = {
        "Representation Similarity": RepresentationSimilarity,
        "TracIn": TracIn,
        "Influence Functions": InfluenceFunctions,
        "SimplEx": SimplEx,
    }
    model_dir = model_dir / model_name
    save_dir = model_dir / "example_importance"
    if not save_dir.exists():
        os.makedirs(save_dir)
    translation = Translation2D(max_displacement)
    metrics = []
    for model_type in models:
        logging.info(f"Now working with {model_type} classifier")
        model = models[model_type]
        model.load_metadata(model_dir)
        model.load_state_dict(torch.load(model_dir / f"{model.name}.pt"), strict=False)
        model.to(device).eval()
        model_inv = model_invariance_exact(model, translation, test_loader, device)
        logging.info(f"Model invariance: {torch.mean(model_inv):.3g}")
        model_layers = {"Lin1": model.fc1, "Conv3": model.cnn3}
        for attr_name in attr_methods:
            logging.info(f"Now working with {attr_name} explainer")
            model.load_state_dict(
                torch.load(model_dir / f"{model.name}.pt"), strict=False
            )
            if attr_name in {"TracIn", "Influence Functions"}:
                ex_importance = attr_methods[attr_name](
                    model,
                    X_train,
                    Y_train=Y_train,
                    train_loader=train_loader_replacement,
                    loss_function=nn.CrossEntropyLoss(),
                    save_dir=save_dir / model.name,
                    recursion_depth=recursion_depth,
                )
                explanation_inv = explanation_invariance_exact(
                    ex_importance, translation, test_loader, device
                )
                for inv_model, inv_expl in zip(model_inv, explanation_inv):
                    metrics.append(
                        [model_type, attr_name, inv_model.item(), inv_expl.item()]
                    )
                logging.info(
                    f"Explanation invariance: {torch.mean(explanation_inv):.3g}"
                )
            else:
                for layer_name in model_layers:
                    ex_importance = attr_methods[attr_name](
                        model, X_train, Y_train=Y_train, layer=model_layers[layer_name]
                    )
                    explanation_inv = explanation_invariance_exact(
                        ex_importance, translation, test_loader, device
                    )
                    ex_importance.remove_hook()
                    for inv_model, inv_expl in zip(model_inv, explanation_inv):
                        metrics.append(
                            [
                                model_type,
                                f"{attr_name}-{layer_name}",
                                inv_model.item(),
                                inv_expl.item(),
                            ]
                        )
                    logging.info(
                        f"Explanation invariance for {layer_name}: {torch.mean(explanation_inv):.3g}"
                    )
    metrics_df = pd.DataFrame(
        data=metrics,
        columns=[
            "Model Type",
            "Explanation",
            "Model Invariance",
            "Explanation Invariance",
        ],
    )
    metrics_df.to_csv(save_dir / "metrics.csv", index=False)
    if plot:
        single_robustness_plots(save_dir, "fashion_mnist", "example_importance")
        relaxing_invariance_plots(save_dir, "fashion_mnist", "example_importance")


def concept_importance(
    random_seed: int,
    latent_dim: int,
    batch_size: int,
    plot: bool,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / "results/fashion_mnist/",
    data_dir: Path = Path.cwd() / "datasets/fashion_mnist",
    n_test: int = 1000,
    concept_set_size: int = 100,
    max_displacement: int = 10,
) -> None:
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    set_random_seed(random_seed)
    train_set = FashionMnistDataset(
        data_dir, train=True, max_displacement=max_displacement
    )
    test_set = FashionMnistDataset(
        data_dir, train=False, max_displacement=max_displacement
    )
    test_subset = Subset(test_set, torch.randperm(len(test_set))[:n_test])
    test_loader = DataLoader(test_subset, batch_size)
    models = {
        "All-CNN": AllCNN(latent_dim, f"{model_name}_allcnn"),
        "Standard-CNN": StandardCNN(latent_dim, f"{model_name}_standard"),
        "Augmented-CNN": StandardCNN(latent_dim, f"{model_name}_augmented"),
    }
    attr_methods = {"CAV": CAV, "CAR": CAR}
    model_dir = model_dir / model_name
    save_dir = model_dir / "concept_importance"
    if not save_dir.exists():
        os.makedirs(save_dir)
    translation = Translation2D(max_displacement)
    metrics = []
    for model_type in models:
        logging.info(f"Now working with {model_type} classifier")
        model = models[model_type]
        model.load_metadata(model_dir)
        model.load_state_dict(torch.load(model_dir / f"{model.name}.pt"), strict=False)
        model.to(device).eval()
        model_inv = model_invariance_exact(model, translation, test_loader, device)
        logging.info(f"Model invariance: {torch.mean(model_inv):.3g}")
        model_layers = {"Lin1": model.fc1, "Conv3": model.cnn3}
        for layer_name, attr_name in itertools.product(model_layers, attr_methods):
            logging.info(
                f"Now working with {attr_name} explainer on layer {layer_name}"
            )
            conc_importance = attr_methods[attr_name](
                model, train_set, n_classes=10, layer=model_layers[layer_name]
            )
            conc_importance.fit(device, concept_set_size)
            concept_acc = conc_importance.concept_accuracy(
                test_set, device, concept_set_size=concept_set_size
            )
            for concept_name in concept_acc:
                logging.info(
                    f"Concept {concept_name} accuracy: {concept_acc[concept_name]:.2g}"
                )
            explanation_inv = explanation_invariance_exact(
                conc_importance, translation, test_loader, device, similarity=accuracy
            )
            conc_importance.remove_hook()
            for inv_model, inv_expl in zip(model_inv, explanation_inv):
                metrics.append(
                    [
                        model_type,
                        f"{attr_name}-{layer_name}",
                        inv_model.item(),
                        inv_expl.item(),
                    ]
                )
            logging.info(f"Explanation invariance: {torch.mean(explanation_inv):.3g}")
    metrics_df = pd.DataFrame(
        data=metrics,
        columns=[
            "Model Type",
            "Explanation",
            "Model Invariance",
            "Explanation Invariance",
        ],
    )
    metrics_df.to_csv(save_dir / "metrics.csv", index=False)
    if plot:
        single_robustness_plots(save_dir, "fashion_mnist", "concept_importance")
        relaxing_invariance_plots(save_dir, "fashion_mnist", "concept_importance")


def enforce_invariance(
    random_seed: int,
    latent_dim: int,
    batch_size: int,
    plot: bool,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / "results/fashion_mnist/",
    data_dir: Path = Path.cwd() / "datasets/fashion_mnist",
    n_test: int = 1000,
    concept_set_size: int = 100,
    max_displacement: int = 10,
) -> None:
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    set_random_seed(random_seed)
    train_set = FashionMnistDataset(
        data_dir, train=True, max_displacement=max_displacement
    )
    test_set = FashionMnistDataset(
        data_dir, train=False, max_displacement=max_displacement
    )
    test_subset = Subset(test_set, torch.randperm(len(test_set))[:n_test])
    test_loader = DataLoader(test_subset, batch_size)
    models = {"All-CNN": AllCNN(latent_dim, f"{model_name}_allcnn")}
    attr_methods = {"CAV": CAV, "CAR": CAR}
    model_dir = model_dir / model_name
    save_dir = model_dir / "enforce_invariance"
    if not save_dir.exists():
        os.makedirs(save_dir)
    translation = Translation2D(5)  # Restrict to a subgroup of translation for runtime
    group_size = len(translation.get_all_symmetries(None))
    metrics = []
    for model_type in models:
        logging.info(f"Now working with {model_type} classifier")
        model = models[model_type]
        model.load_metadata(model_dir)
        model.load_state_dict(torch.load(model_dir / f"{model.name}.pt"), strict=False)
        model.to(device).eval()
        model_inv = model_invariance_exact(model, translation, test_loader, device)
        logging.info(f"Model invariance: {torch.mean(model_inv):.3g}")
        for attr_name in attr_methods:
            logging.info(f"Now working with {attr_name} explainer")
            attr_method = attr_methods[attr_name](
                model, train_set, n_classes=10, layer=model.cnn3
            )
            if isinstance(attr_method, ConceptExplainer):
                attr_method.fit(device, concept_set_size)
            for N_inv in [
                1,
                10,
                int(group_size / 4),
                int(3 * group_size / 4),
                int(group_size),
            ]:
                logging.info(
                    f"Now working with invariant explainer with N_inv = {N_inv}"
                )
                inv_method = InvariantExplainer(
                    attr_method,
                    AnchoredTranslation2D(
                        5
                    ),  # This group handles composition of translations
                    N_inv,
                    isinstance(attr_method, ConceptExplainer),
                )
                explanation_inv = explanation_invariance_exact(
                    inv_method, translation, test_loader, device, similarity=accuracy
                )
                logging.info(
                    f"N_inv = {N_inv} - Explanation invariance = {torch.mean(explanation_inv):.3g}"
                )
                for inv_expl in explanation_inv:
                    metrics.append(
                        [model_type, f"{attr_name}-Equiv", N_inv, inv_expl.item()]
                    )
    metrics_df = pd.DataFrame(
        data=metrics,
        columns=["Model Type", "Explanation", "N_inv", "Explanation Invariance"],
    )
    metrics_df.to_csv(save_dir / "metrics.csv", index=False)
    if plot:
        enforce_invariance_plot(save_dir, "fashion_mnist")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="feature_importance")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch_size", type=int, default=500)
    parser.add_argument("--latent_dim", type=int, default=32)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--n_test", type=int, default=500)
    args = parser.parse_args()
    model_name = f"cnn{args.latent_dim}_seed{args.seed}"
    if args.train:
        train_fashion_mnist_model(
            args.seed, args.latent_dim, args.batch_size, model_name=model_name
        )
    match args.name:
        case "feature_importance":
            feature_importance(
                args.seed,
                args.latent_dim,
                args.plot,
                model_name,
                batch_size=args.batch_size,
                n_test=args.n_test,
            )
        case "example_importance":
            example_importance(
                args.seed,
                args.latent_dim,
                args.batch_size,
                args.plot,
                model_name,
                n_test=args.n_test,
            )
        case "concept_importance":
            concept_importance(
                args.seed,
                args.latent_dim,
                args.batch_size,
                args.plot,
                model_name,
                n_test=args.n_test,
            )
        case "enforce_invariance":
            enforce_invariance(
                args.seed,
                args.latent_dim,
                args.batch_size,
                args.plot,
                model_name,
                n_test=args.n_test,
            )
        case other:
            raise ValueError("Invalid experiment name.")
