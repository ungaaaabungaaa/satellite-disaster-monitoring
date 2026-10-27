export function classifyIndices(before, after, threshold) {
  if (
    !(before instanceof Float32Array) ||
    !(after instanceof Float32Array) ||
    before.length !== after.length ||
    before.length < 1 ||
    before.length > 2_000_000 ||
    !Number.isFinite(threshold) ||
    threshold < -1 ||
    threshold > 1
  ) {
    throw new Error("Invalid index arrays or threshold.");
  }
  const cutoff = Math.fround(threshold);
  const classes = new Uint8Array(before.length);
  const counts = {
    common: 0,
    before: 0,
    after: 0,
    gain: 0,
    loss: 0,
    persistent: 0,
  };
  for (let i = 0; i < before.length; i++) {
    const old = before[i],
      next = after[i];
    if (
      !Number.isFinite(old) ||
      !Number.isFinite(next) ||
      Math.abs(old) > 1 ||
      Math.abs(next) > 1
    )
      continue;
    counts.common++;
    const waterBefore = old > cutoff,
      waterAfter = next > cutoff;
    if (waterBefore) counts.before++;
    if (waterAfter) counts.after++;
    if (waterBefore && waterAfter) {
      classes[i] = 2;
      counts.persistent++;
    } else if (waterAfter) {
      classes[i] = 3;
      counts.gain++;
    } else if (waterBefore) {
      classes[i] = 4;
      counts.loss++;
    } else classes[i] = 1;
  }
  return { classes, counts };
}
