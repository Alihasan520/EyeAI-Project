# EyeAI Run 09 + TTA model limitations

EyeAI is an AI-assisted binary AMD screening prototype. It is not an autonomous diagnosis system.

The selected inference model is RETFound Run 09 with original-image and horizontal-flip test-time augmentation. The decision threshold is 0.335.

A change in the model score does not independently confirm disease progression. Image acquisition, camera domain, illumination, field of view, and image quality may affect the score.

The attribution heatmap shows image regions that influenced the model output. It is not a lesion segmentation map and does not independently establish lesion location or disease severity.

Clinical review and confirmatory assessment are required.
