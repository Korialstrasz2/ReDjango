import { readdir, rm } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const frontendDirectory = path.resolve(scriptDirectory, "..");
const testsDirectory = path.join(frontendDirectory, "tests");
const resultsDirectory = path.join(frontendDirectory, "test-results", "desktop-isolated");

const excluded = [
  /^mobile-/,
  /^desktop-visual-/,
  /^auth\.setup\.ts$/,
];

const entries = await readdir(testsDirectory, { withFileTypes: true });
const specs = entries
  .filter((entry) => entry.isFile() && entry.name.endsWith(".spec.ts"))
  .map((entry) => entry.name)
  .filter((name) => !excluded.some((pattern) => pattern.test(name)))
  .sort();

if (!specs.length) throw new Error("No canonical desktop specs were discovered.");
await rm(resultsDirectory, { recursive: true, force: true });

function runSpec(spec) {
  const stem = spec.replace(/\.spec\.ts$/, "");
  const output = path.join("test-results", "desktop-isolated", stem);
  const args = [
    "playwright",
    "test",
    path.join("tests", spec),
    "--project=authenticated",
    "--workers=1",
    "--reporter=line",
    `--output=${output}`,
  ];

  return new Promise((resolve) => {
    const command = process.platform === "win32" ? "npx.cmd" : "npx";
    const child = spawn(command, args, {
      cwd: frontendDirectory,
      env: { ...process.env, PLAYWRIGHT_HTML_OPEN: "never" },
      stdio: "inherit",
    });
    child.on("error", (error) => resolve({ spec, status: 1, error }));
    child.on("exit", (status, signal) => resolve({ spec, status: status ?? 1, signal }));
  });
}

const failures = [];
console.log(`Running ${specs.length} canonical desktop specs with a fresh seeded server per file.`);
for (const [index, spec] of specs.entries()) {
  console.log(`\n[desktop ${index + 1}/${specs.length}] ${spec}`);
  const result = await runSpec(spec);
  if (result.status !== 0) failures.push(result);
}

if (failures.length) {
  console.error("\nCanonical desktop failures:");
  for (const failure of failures) {
    console.error(`- ${failure.spec} (exit ${failure.status}${failure.signal ? `, signal ${failure.signal}` : ""})`);
    if (failure.error) console.error(failure.error);
  }
  process.exitCode = 1;
} else {
  console.log("\nAll canonical desktop specs passed on isolated seeded databases.");
}
