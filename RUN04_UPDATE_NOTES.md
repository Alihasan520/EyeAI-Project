# Run 04 Smart Multi-ROI — Black Corner Fix v2

## Problem fixed
The previous black-background fix used median retinal color to fill outside-retina black pixels after ROI cropping. Visual inspection showed this created artificial reddish/brown background blocks and dark circular borders. This is not acceptable for training.

## New approach
This update removes artificial color filling completely.

Instead, Run 04 now uses:

- `black_fill_mode: none`
- safer ROI specs that stay closer to the retinal center
- `avoid_black_roi: true`
- automatic ROI scale shrinking when a crop still contains too many near-black pixels

The goal is to avoid black-corner artifacts without inventing synthetic background colors.

## Important config values

```yaml
black_fill_mode: none
black_threshold: 8
avoid_black_roi: true
max_black_fraction: 0.015
min_roi_scale: 0.45
```

## Updated ROI list

```yaml
roi_specs:
  - {name: center_065, cx: 0.50, cy: 0.50, scale: 0.65}
  - {name: center_055, cx: 0.50, cy: 0.50, scale: 0.55}
  - {name: left_055, cx: 0.43, cy: 0.50, scale: 0.55}
  - {name: right_055, cx: 0.57, cy: 0.50, scale: 0.55}
  - {name: upper_055, cx: 0.50, cy: 0.43, scale: 0.55}
  - {name: lower_055, cx: 0.50, cy: 0.57, scale: 0.55}
```

## What to verify before training
Run the notebook visual-check cell and confirm:

1. There are no artificial reddish/brown square backgrounds.
2. Near-black outside-retina corners are mostly gone.
3. The displayed black fraction is low for ROI views.
4. ROI crops still preserve clinically useful retinal texture.

Do not start training if ROI crops still show large black-corner artifacts.
