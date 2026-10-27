import test from "node:test";
import assert from "node:assert/strict";
import { classifyIndices } from "../src/satellite_monitoring/resources/viewer/classification.mjs";

test("counts only the common valid footprint and preserves class meanings", () => {
  const result = classifyIndices(
    new Float32Array([0.2, -0.2, 0.2, -0.2, NaN]),
    new Float32Array([0.2, 0.2, -0.2, -0.2, 0.4]),
    0,
  );
  assert.deepEqual([...result.classes], [2, 3, 4, 1, 0]);
  assert.deepEqual(result.counts, {
    common: 4,
    before: 2,
    after: 2,
    gain: 1,
    loss: 1,
    persistent: 1,
  });
});
test("threshold equality uses float32 semantics matching NumPy arrays", () => {
  const result = classifyIndices(
    new Float32Array([0.1, 0.1001]),
    new Float32Array([0.1, 0.1001]),
    0.1,
  );
  assert.equal(result.counts.before, 1);
});
test("bounds and nonfinite indices cannot become candidate water", () => {
  assert.throws(() =>
    classifyIndices(new Float32Array(2), new Float32Array(1), 0),
  );
  assert.throws(() =>
    classifyIndices(new Float32Array(1), new Float32Array(1), Infinity),
  );
  assert.equal(
    classifyIndices(
      new Float32Array([Infinity, 2]),
      new Float32Array([0.5, 0.5]),
      0,
    ).counts.common,
    0,
  );
});
