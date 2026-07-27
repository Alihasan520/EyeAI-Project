import unittest

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from eyeai.data.prepare_binary_dataset import _assign_hyamd_split_groups, _split_external_manifest
from eyeai.data.samplers import build_training_sampler
from eyeai.inference.ensemble import weighted_average_predictions
from eyeai.postprocessing.thresholds import optimize_binary_threshold
from eyeai.models.retfound_finetune import (
    build_retfound_optimizer_groups,
    interpolate_position_embedding,
    set_retfound_trainability,
)
from eyeai.training.train_binary import positive_only_metrics


class BinaryPipelineV2Tests(unittest.TestCase):
    def test_source_aware_sampler_targets(self):
        frame = pd.DataFrame(
            ([{"binary_label": 0, "dataset_source": "hyamd"}] * 20)
            + ([{"binary_label": 1, "dataset_source": "hyamd"}] * 10)
            + ([{"binary_label": 1, "dataset_source": "armd_curated"}] * 15)
        )
        sampler, report = build_training_sampler(
            frame,
            mode="source_aware",
            positive_fraction=0.50,
            external_positive_fraction=0.35,
            num_samples=20000,
            seed=42,
        )
        sampled = frame.iloc[list(iter(sampler))]
        observed = sampled.groupby(["binary_label", "dataset_source"]).size() / len(sampled)
        self.assertAlmostEqual(observed.loc[(0, "hyamd")], 0.50, delta=0.02)
        self.assertAlmostEqual(observed.loc[(1, "hyamd")], 0.325, delta=0.02)
        self.assertAlmostEqual(observed.loc[(1, "armd_curated")], 0.175, delta=0.02)
        self.assertEqual(report["mode"], "source_aware")

    def test_ensemble_aligns_by_image_id(self):
        left = pd.DataFrame({
            "image_id": ["a", "b"],
            "binary_label": [0, 1],
            "prob_amd": [0.1, 0.9],
        })
        right = pd.DataFrame({
            "image_id": ["b", "a"],
            "binary_label": [1, 0],
            "prob_amd": [0.7, 0.3],
        })
        result = weighted_average_predictions([left, right], [0.5, 0.5])
        self.assertEqual(result["image_id"].tolist(), ["a", "b"])
        np.testing.assert_allclose(result["prob_amd"].to_numpy(), [0.2, 0.8])

    def test_exact_duplicate_patients_share_split_group(self):
        frame = pd.DataFrame({
            "patient_id": ["p1", "p2", "p3"],
            "sha256": ["same", "same", "other"],
            "binary_label": [0, 0, 1],
        })
        grouped = _assign_hyamd_split_groups(frame)
        self.assertEqual(grouped.loc[0, "split_group_id"], grouped.loc[1, "split_group_id"])
        self.assertNotEqual(grouped.loc[0, "split_group_id"], grouped.loc[2, "split_group_id"])

    def test_threshold_optimization_returns_valid_threshold(self):
        result = optimize_binary_threshold(
            y_true=[0, 0, 1, 1],
            y_prob=[0.1, 0.4, 0.6, 0.9],
            grid_step=0.05,
            mode="balanced",
        )
        self.assertGreaterEqual(result["threshold"], 0.0)
        self.assertLessEqual(result["threshold"], 1.0)
        self.assertIn("macro_f1", result["metrics"])

    def test_external_validation_split_has_no_group_overlap(self):
        frame = pd.DataFrame({
            "image_id": [f"e{i}" for i in range(20)],
            "split_group_id": [f"g{i}" for i in range(20)],
            "sha256": [f"h{i}" for i in range(20)],
            "binary_label": [1] * 20,
        })
        train_df, val_df = _split_external_manifest(frame, validation_fraction=0.10, seed=42)
        self.assertEqual(len(train_df) + len(val_df), 20)
        self.assertFalse(set(train_df["split_group_id"]) & set(val_df["split_group_id"]))
        self.assertFalse(set(train_df["sha256"]) & set(val_df["sha256"]))

    def test_retfound_last_six_trainability(self):
        class DummyRETFound(nn.Module):
            def __init__(self):
                super().__init__()
                self.patch_embed = nn.Linear(2, 2)
                self.blocks = nn.ModuleList([nn.Linear(2, 2) for _ in range(24)])
                self.fc_norm = nn.LayerNorm(2)
                self.norm = nn.Identity()
                self.head = nn.Linear(2, 2)

        model = DummyRETFound()
        report = set_retfound_trainability(model, unfreeze_last_blocks=6)
        self.assertEqual(report["trainable_block_indices"], list(range(18, 24)))
        self.assertFalse(any(parameter.requires_grad for parameter in model.blocks[17].parameters()))
        self.assertTrue(all(parameter.requires_grad for parameter in model.blocks[18].parameters()))
        self.assertTrue(all(parameter.requires_grad for parameter in model.head.parameters()))

        groups = build_retfound_optimizer_groups(
            model,
            model_config={},
            train_config={
                "lr": 2e-5,
                "head_lr": 1e-4,
                "layer_decay": 0.75,
                "weight_decay": 0.05,
            },
        )
        self.assertTrue(groups)
        self.assertTrue(any(group["group_name"] == "retfound_head" for group in groups))
        self.assertTrue(all(group["lr"] > 0 for group in groups))


    def test_retfound_position_embedding_interpolation(self):
        class DummyPatchEmbed:
            num_patches = 9

        class DummyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.patch_embed = DummyPatchEmbed()
                self.pos_embed = nn.Parameter(torch.zeros(1, 10, 4))

        model = DummyModel()
        state_dict = {"pos_embed": torch.randn(1, 5, 4)}
        changed = interpolate_position_embedding(model, state_dict)
        self.assertTrue(changed)
        self.assertEqual(tuple(state_dict["pos_embed"].shape), (1, 10, 4))

    def test_positive_only_metrics(self):
        predictions = pd.DataFrame({"prob_amd": [0.2, 0.6, 0.9]})
        metrics = positive_only_metrics(predictions, threshold=0.5)
        self.assertAlmostEqual(metrics["recall_amd"], 2 / 3)
        self.assertAlmostEqual(metrics["mean_probability"], 0.5666666667)


if __name__ == "__main__":
    unittest.main()
