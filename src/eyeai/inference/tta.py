from typing import List

from PIL import Image
from torchvision import transforms as T

from eyeai.data.transforms import IMAGENET_MEAN, IMAGENET_STD, _interpolation_mode


def apply_tta_variant(image: Image.Image, variant: str) -> Image.Image:
    image = image.convert("RGB")
    if variant == "original":
        return image
    if variant == "hflip":
        return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    raise ValueError(
        f"Unsupported TTA variant: {variant}. Rotation TTA is disabled because it creates new border pixels."
    )


def build_tta_transforms(
    image_size: int,
    variants: List[str],
    mean=None,
    std=None,
    interpolation: str = "bilinear",
):
    base = T.Compose([
        T.Resize((image_size, image_size), interpolation=_interpolation_mode(interpolation)),
        T.ToTensor(),
        T.Normalize(mean=mean or IMAGENET_MEAN, std=std or IMAGENET_STD),
    ])

    def transform(image: Image.Image):
        return [base(apply_tta_variant(image, variant)) for variant in variants]

    return transform
