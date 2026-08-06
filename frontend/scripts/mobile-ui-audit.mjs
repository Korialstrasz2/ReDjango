import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const frontendDirectory = path.resolve(scriptDirectory, "..");
const sourceDirectory = path.join(frontendDirectory, "src");
const outputDirectory = path.join(frontendDirectory, "test-results", "mobile-ui-audit");

const categories = {
  sharedModal: /<Modal\b/,
  toolDrawer: /<ToolDrawer\b/,
  portal: /\bcreatePortal\s*\(/,
  semanticDialog: /role=["'{]dialog\b|role\s*=\s*["']dialog["']/,
  nativeConfirm: /\bwindow\.(?:confirm|alert|prompt)\s*\(/,
  hoverSelector: /:hover\b/,
  titleAttribute: /\btitle\s*=\s*(?:["'{])/,
  mouseHandler: /\bonMouse(?:Enter|Leave|Down|Move|Up|Over|Out)\s*=/,
  pointerHandler: /\bonPointer(?:Enter|Leave|Down|Move|Up|Over|Out|Cancel)\s*=/,
  contextMenu: /\bonContextMenu\s*=/,
  touchAction: /\btouch-action\s*:/,
  fixedPosition: /\bposition\s*:\s*fixed\b/,
  stickyPosition: /\bposition\s*:\s*sticky\b/,
  horizontalOverflow: /\boverflow-x\s*:/,
};

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await walk(absolute));
    else if (/\.(?:css|scss|ts|tsx)$/.test(entry.name)) files.push(absolute);
  }
  return files;
}

const files = await walk(sourceDirectory);
if (!files.length) throw new Error(`No source files found under ${sourceDirectory}`);

const findings = [];
for (const absolute of files) {
  const relative = path.relative(frontendDirectory, absolute).split(path.sep).join("/");
  const lines = (await readFile(absolute, "utf8")).split(/\r?\n/);
  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("//")) return;
    for (const [category, expression] of Object.entries(categories)) {
      if (!expression.test(line)) continue;
      findings.push({ category, file: relative, line: index + 1, text: trimmed.slice(0, 500) });
    }
  });
}

findings.sort((left, right) => left.category.localeCompare(right.category)
  || left.file.localeCompare(right.file)
  || left.line - right.line);

const counts = Object.fromEntries(Object.keys(categories).map((category) => [
  category,
  findings.filter((finding) => finding.category === category).length,
]));
const report = {
  generatedAt: new Date().toISOString(),
  sourceDirectory: "src",
  scannedFiles: files.length,
  counts,
  findings,
  classificationRequired: [
    "Every modal, drawer, portal, semantic dialog, and native browser prompt needs desktop/phone/tablet behavior recorded.",
    "Every hover, title-only, mouse, pointer, and context-menu interaction needs a visible tap or focus alternative where user-facing.",
    "Every touch-action declaration needs scrolling and drag arbitration evidence.",
    "Every fixed/sticky element and horizontal scroller needs viewport and fixed-chrome containment evidence.",
  ],
};

await mkdir(outputDirectory, { recursive: true });
await writeFile(path.join(outputDirectory, "mobile-ui-audit.json"), `${JSON.stringify(report, null, 2)}\n`);

const markdown = [
  "# Mobile UI Source Audit",
  "",
  `Generated: ${report.generatedAt}`,
  `Scanned source files: ${report.scannedFiles}`,
  "",
  "This report enumerates candidate call sites. A finding is not automatically a defect, and absence from a category is not release approval. Each user-facing finding must be classified in the mobile inventory and release ledger.",
  "",
  "## Counts",
  "",
  "| Category | Count |",
  "| --- | ---: |",
  ...Object.entries(counts).map(([category, count]) => `| ${category} | ${count} |`),
  "",
  "## Findings",
  "",
  ...Object.keys(categories).flatMap((category) => {
    const rows = findings.filter((finding) => finding.category === category);
    return [
      `### ${category}`,
      "",
      ...(rows.length ? rows.map((finding) => `- \`${finding.file}:${finding.line}\` — \`${finding.text.replaceAll("`", "\\`")}\``) : ["- None found."]),
      "",
    ];
  }),
];
await writeFile(path.join(outputDirectory, "mobile-ui-audit.md"), `${markdown.join("\n")}\n`);

console.log(`Mobile UI audit scanned ${files.length} files and recorded ${findings.length} findings.`);
for (const [category, count] of Object.entries(counts)) console.log(`${category}: ${count}`);
