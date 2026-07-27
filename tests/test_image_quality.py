from PIL import Image, ImageDraw, ImageFilter

from eyeai.inference.image_quality import assess_fundus_image_quality


def _fundus_like_image(size: int = 768) -> Image.Image:
    image = Image.new("RGB", (size, size), "black")
    draw = ImageDraw.Draw(image)
    margin = size // 12
    draw.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=(150, 65, 45),
    )
    return image


def test_quality_accepts_basic_fundus_like_image():
    image = _fundus_like_image()
    result = assess_fundus_image_quality(image, image)
    assert result.processable is True
    assert result.metrics["fundus_fraction"] > 0.45
    assert "low_input_resolution" not in result.warnings


def test_quality_warns_for_low_resolution_and_glare():
    image = _fundus_like_image(256)
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 130, 220), fill="white")
    result = assess_fundus_image_quality(image, image)
    assert "low_input_resolution" in result.warnings
    assert "possible_glare" in result.warnings


def test_quality_warns_for_blur():
    image = _fundus_like_image().filter(ImageFilter.GaussianBlur(radius=30))
    result = assess_fundus_image_quality(
        image,
        image,
        {"minimum_laplacian_variance": 100.0},
    )
    assert "possible_blur" in result.warnings
