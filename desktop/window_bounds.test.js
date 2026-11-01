const { test } = require("node:test");
const assert = require("node:assert/strict");
const { clampWindowBounds } = require("./window_bounds");

const PRIMARY = { x: 0, y: 0, width: 1920, height: 1040 };
const SECONDARY = { x: 1920, y: 0, width: 1920, height: 1080 };

test("pulls negative x back onto the work area", () => {
  assert.deepEqual(
    clampWindowBounds({ x: -84, y: 304, width: 921, height: 640 }, [PRIMARY]),
    { x: 0, y: 304, width: 921, height: 640 },
  );
});

test("centers when stored origin is missing", () => {
  const bounds = clampWindowBounds({ width: 920, height: 640 }, [PRIMARY]);
  assert.equal(bounds.x, Math.floor((1920 - 920) / 2));
  assert.equal(bounds.y, Math.floor((1040 - 640) / 2));
  assert.equal(bounds.width, 920);
  assert.equal(bounds.height, 640);
});

test("keeps a window that already sits on the second display", () => {
  assert.deepEqual(
    clampWindowBounds({ x: 2100, y: 100, width: 920, height: 640 }, [PRIMARY, SECONDARY]),
    { x: 2100, y: 100, width: 920, height: 640 },
  );
});

test("moves a fully off-screen window onto the nearest display", () => {
  assert.deepEqual(
    clampWindowBounds({ x: -5000, y: 100, width: 920, height: 640 }, [PRIMARY]),
    { x: 0, y: 100, width: 920, height: 640 },
  );
});

test("shrinks an oversized window to the work area", () => {
  assert.deepEqual(clampWindowBounds({ x: 0, y: 0, width: 3000, height: 2000 }, [PRIMARY]), {
    x: 0,
    y: 0,
    width: 1920,
    height: 1040,
  });
});
