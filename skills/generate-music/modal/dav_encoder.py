"""PyTorch implementation of the MiniMax Music 3 DAV posterior-mean encoder."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn.utils import weight_norm


class Snake1d(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.alpha = nn.Parameter(torch.ones(1, channels, 1))

    def forward(self, x: Tensor) -> Tensor:
        alpha = self.alpha
        return x + (alpha + 1e-9).reciprocal() * torch.sin(alpha * x).pow(2)


def _wn_conv1d(
    in_channels: int,
    out_channels: int,
    kernel_size: int,
    *,
    stride: int = 1,
    padding: int = 0,
    dilation: int = 1,
) -> nn.Conv1d:
    # Legacy weight_norm preserves the checkpoint's weight_g/weight_v names.
    return weight_norm(
        nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )
    )


class ResidualUnit(nn.Module):
    def __init__(self, channels: int, dilation: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            Snake1d(channels),
            _wn_conv1d(channels, channels, 7, padding=3 * dilation, dilation=dilation),
            Snake1d(channels),
            _wn_conv1d(channels, channels, 1),
        )

    def forward(self, x: Tensor) -> Tensor:
        return x + self.block(x)


class EncoderBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            ResidualUnit(in_channels, 1),
            ResidualUnit(in_channels, 3),
            ResidualUnit(in_channels, 9),
            Snake1d(in_channels),
            _wn_conv1d(in_channels, out_channels, 2 * stride, stride=stride, padding=stride // 2),
        )

    def forward(self, x: Tensor) -> Tensor:
        return self.block(x)


class DAVEncoder(nn.Module):
    """DAV encoder whose state dictionary matches encoder.* and mean_proj.* keys."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Module()
        self.encoder.block = nn.Sequential(
            _wn_conv1d(1, 64, 7, padding=3),
            EncoderBlock(64, 128, 2),
            EncoderBlock(128, 256, 4),
            EncoderBlock(256, 512, 8),
            EncoderBlock(512, 1024, 8),
            Snake1d(1024),
            _wn_conv1d(1024, 1024, 3, padding=1),
        )
        self.mean_proj = nn.Conv1d(1024, 64, 1)

    def forward(self, x: Tensor) -> Tensor:
        return self.mean_proj(self.encoder.block(x))


def _extract_state_dict(checkpoint: Any) -> dict[str, Tensor]:
    if isinstance(checkpoint, Mapping):
        for key in ("state_dict", "model_state_dict", "model"):
            value = checkpoint.get(key)
            if isinstance(value, Mapping):
                checkpoint = value
                break
    if not isinstance(checkpoint, Mapping):
        raise TypeError("Checkpoint does not contain a state dictionary")
    return {key: value for key, value in checkpoint.items() if isinstance(key, str) and torch.is_tensor(value)}


def _remap_weight_norm_keys(state_dict: Mapping[str, Tensor]) -> dict[str, Tensor]:
    remapped: dict[str, Tensor] = {}
    for key, value in state_dict.items():
        key = key.replace(".parametrizations.weight.original0", ".weight_g")
        key = key.replace(".parametrizations.weight.original1", ".weight_v")
        remapped[key] = value
    return remapped


def load_dav_encoder(path: str | Path, *, map_location: Any = "cpu") -> DAVEncoder:
    """Load DAV's encoder and posterior mean projection from a checkpoint file."""
    try:
        checkpoint = torch.load(path, map_location=map_location, weights_only=True)
    except TypeError:
        checkpoint = torch.load(path, map_location=map_location)
    state_dict = _remap_weight_norm_keys(_extract_state_dict(checkpoint))
    state_dict = {
        key: value
        for key, value in state_dict.items()
        if key.startswith(("encoder.", "mean_proj."))
    }
    model = DAVEncoder()
    model.load_state_dict(state_dict, strict=True)
    return model
