# Method and limits

The study compares spectral water candidates on two historical images. The processing contains no trained model, live data feed, disaster prediction, calibrated probability, or ground-truth accuracy evaluation.

## Inputs and alignment

Each bounded local GeoTIFF has six bands, nodata 0, projected metre coordinates, a finite north-up unrotated transform, an aware timestamp, a source ID, and scale/offset tags. The default products share the exact 20 m EPSG:32645 grid. For other valid inputs, the second date is reprojected to the first grid: average for optical DN bands, nearest for SCL and RGB. Out-of-coverage pixels become nodata. Interpolation, resolution changes, and boundary mixed pixels can affect custom results; they are explicitly marked `custom-unverified`.

Raw DN 0 is invalid before scaling, including with a positive offset. Effective reflectance is `DN × scale + offset`. Valid index inputs require finite positive green and SWIR reflectance and a finite positive sum. The denominator guard prevents division by zero and non-finite results.

## Quality footprint

Retain SCL 4 (vegetation), 5 (not vegetated), or 6 (water). Exclude 0 (nodata), 1 (defective/saturated), 2 (dark/topographic shadow), 3 (cloud shadow), 7 (unclassified), 8/9 (cloud), 10 (cirrus), and 11 (snow/ice). See the provider's [scene-classification reference](https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/scene-classification/). These classes are an imperfect processing product, not independent water labels.

The comparison mask is the intersection of each date's quality and optical-validity masks. All before/after water, persistent water, gain, loss, and stable-land counts use this same mask. The default common footprint is only 427,550 / 1,163,999 pixels (36.73%). The other 63.27% is excluded, never treated as dry land or scaled into the estimate.

## Index, classes, and area

MNDWI = `(green − SWIR) / (green + SWIR)`. A pixel is a water candidate only if its index is **strictly greater** than the selected threshold. Fixed sensitivity values are −0.1, 0.0, 0.1, 0.2, and 0.3. The browser uses exact saved float32 values and a float32 threshold, then checks its counts against Python for every preset. This avoids display quantization changing classification near a threshold.

Classification codes: 0 excluded, 1 stable land, 2 persistent candidate water, 3 candidate gain, 4 candidate loss. `before = persistent + loss`, `after = persistent + gain`, and `common = stable land + persistent + gain + loss`. The exported `change.tif` always uses threshold 0.00; the viewer labels this fixed download separately from its interactive threshold.

Pixel area is the absolute affine determinant in square metres, then divided by 1,000,000 for km². Geographic degrees and non-metre input CRSs are rejected. Areas represent the projected grid, without a separate projection-distortion or geodesic correction. The default cell is 400 m². The WGS84 GeoJSON has a counter-clockwise exterior ring.

## Interpretation

The February/August pair includes normal seasonal change. [NASA's account of the 2020 Bangladesh monsoon flooding](https://science.nasa.gov/earth/earth-observatory/intense-flooding-in-bangladesh-147057/) documents regional conditions; it does not prove that a candidate gain in this crop was caused by that event. There are no reference flood polygons or field labels in this project. No precision, recall, IoU, damage estimate, or confirmed flood-area claim is made.

Wet soil, sediment, turbidity, built surfaces, mixed pixels, thin clouds, cloud shadows, classification errors, and resampling can produce false positives or omissions. Choice of threshold changes the result: candidate gain varies from 82.6180 to 108.1472 km² across the five presets. This spread is sensitivity evidence, not a confidence interval. Do not use this study for an evacuation, insurance, or other operational decision.

The imagery, index arrays, and area figures are actual processed data. The README line-art cover is generated concept art and is labeled separately.
