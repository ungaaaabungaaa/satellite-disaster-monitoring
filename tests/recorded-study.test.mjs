import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { createHash } from "node:crypto";
import { classifyIndices } from "../src/satellite_monitoring/resources/viewer/classification.mjs";

test("browser classification reproduces all five recorded real-study thresholds", async () => {
  const root = new URL("../demo/", import.meta.url);
  const report = JSON.parse(await readFile(new URL("data.json", root), "utf8"));
  const values = [];
  for (const side of ["before", "after"]) {
    const name = `${side}.f32.gz`,
      compressed = await readFile(new URL(name, root));
    assert.equal(
      createHash("sha256").update(compressed).digest("hex"),
      report.asset_sha256[name],
    );
    const bytes = gunzipSync(compressed),
      view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    assert.equal(bytes.length, report.width * report.height * 4);
    const index = new Float32Array(bytes.length / 4);
    for (let i = 0; i < index.length; i++)
      index[i] = view.getFloat32(i * 4, true);
    values.push(index);
  }
  for (const row of report.thresholds) {
    const { counts } = classifyIndices(...values, row.threshold);
    for (const [js, python] of [
      ["common", "common_valid_pixels"],
      ["before", "before_water_pixels"],
      ["after", "after_water_pixels"],
      ["gain", "gain_pixels"],
      ["loss", "loss_pixels"],
    ]) {
      assert.equal(
        counts[js],
        row[python],
        `${js} at threshold ${row.threshold}`,
      );
    }
  }
});
