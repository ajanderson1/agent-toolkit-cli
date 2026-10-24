// Hold Pi's own lock protocol while Python runs an external npm operation.
// Infinity refuses even old locks; updates keep native Pi from stealing ours.
import { createRequire } from "node:module";
import { once } from "node:events";
import { join } from "node:path";

try {
  const require = createRequire(join(process.argv[2], "package.json"));
  const lockfile = require("proper-lockfile");
  const release = await lockfile.lock(process.argv[3], {
    realpath: false, stale: Infinity, update: 1000, retries: 0,
    onCompromised(error) { console.error(error.message); process.exit(2); },
  });
  const ended = once(process.stdin, "end");
  process.stdout.write("locked\n");
  process.stdin.resume();
  await ended;
  await release();
} catch (error) {
  console.error(error.code === "ELOCKED" ? "settings are locked; retry after Pi finishes saving" : error.message);
  process.exitCode = 1;
}
