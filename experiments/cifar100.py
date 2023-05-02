import pytorch_lightning as pl
import argparse
import torch
import logging
import os
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
from models.images import Wide_ResNet
from datasets.loaders import Cifar100Dataset
from pathlib import Path
from utils.misc import set_random_seed
from utils.symmetries import Dihedral
from captum.attr import (
    DeepLift,
    IntegratedGradients,
    GradientShap,
    FeaturePermutation,
    FeatureAblation,
    Occlusion,
)
from interpretability.feature import FeatureImportance
from interpretability.robustness import model_invariance_exact


def train_cifar100_model(
    random_seed: int,
    batch_size: int,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / f"results/cifar100/",
    data_dir: Path = Path.cwd() / "datasets/cifar100",
    use_wandb: bool = False,
) -> None:
    set_random_seed(random_seed)
    model_dir = model_dir / model_name
    model = Wide_ResNet()
    datamodule = Cifar100Dataset(data_dir=data_dir, batch_size=batch_size)
    logger = (
        pl.loggers.WandbLogger(project="RobustXAI", name=model_name, save_dir=model_dir)
        if use_wandb
        else None
    )
    callbacks = [
        ModelCheckpoint(
            dirpath=model_dir,
            monitor="val/acc",
            every_n_epochs=10,
            save_top_k=-1,
            filename=model_name + "-{epoch:02d}-{val_acc:.2f}",
        ),
        EarlyStopping(monitor="val/acc", patience=10, mode="max"),
    ]
    trainer = pl.Trainer(
        logger=logger,
        max_epochs=200,
        default_root_dir=model_dir,
        callbacks=callbacks,
    )
    trainer.fit(model, datamodule=datamodule)
    trainer.test(model, ckpt_path="best", datamodule=datamodule)


def feature_importance(
    random_seed: int,
    batch_size: int,
    model_name: str = "model",
    model_dir: Path = Path.cwd() / f"results/cifar100/",
    data_dir: Path = Path.cwd() / "datasets/cifar100",
    plot: bool = True,
    n_test: int = 500,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    set_random_seed(random_seed)
    model_dir = model_dir / model_name
    datamodule = Cifar100Dataset(
        data_dir=data_dir, batch_size=batch_size, num_predict=n_test
    )
    datamodule.setup("predict")
    test_loader = datamodule.predict_dataloader()
    dihedral_group = Dihedral()
    models = {
        "D8 Wide ResNet": Wide_ResNet()  # TODO .load_from_checkpoint(get_best_checkpoint(model_dir)
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
    metrics = []
    for model_type, model in models.items():
        logging.info(f"Now working with {model_type} classifier")
        model.to(device).eval()
        model_inv = model_invariance_exact(model, dihedral_group, test_loader, device)
        logging.info(f"Model invariance: {torch.mean(model_inv):.3g}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch_size", type=int, default=50)
    parser.add_argument("--use_wandb", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--name", type=str, default="feature importance")
    parser.add_argument("--n_test", type=int, default=500)
    args = parser.parse_args()
    model_name = f"cifar100_d8_wideresnet_seed{args.seed}"
    if args.train:
        train_cifar100_model(
            random_seed=args.seed,
            batch_size=args.batch_size,
            use_wandb=args.use_wandb,
            model_name=model_name,
        )
    match args.name:
        case "feature importance":
            feature_importance(
                random_seed=args.seed,
                batch_size=args.batch_size,
                model_name=model_name,
                plot=args.plot,
                n_test=args.n_test,
            )
        case other:
            raise NotImplementedError(f"Experiment {args.name} does not exist.")
