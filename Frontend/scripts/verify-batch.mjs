import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const required = [
  "src/pages/AssistantPage.tsx",
  "src/pages/ReportsPage.tsx",
  "src/pages/AlertsPage.tsx",
  "src/components/analysis/ImageReviewModal.tsx",
];

for (const relative of required) {
  const path = resolve(root, relative);
  if (!existsSync(path)) throw new Error(`Missing Batch 04.2 file: ${relative}`);
}

const packageJson = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8"));
if (packageJson.version !== "0.4.2") {
  throw new Error(`Expected frontend version 0.4.2, found ${packageJson.version}`);
}

const app = readFileSync(resolve(root, "src/App.tsx"), "utf8");
for (const route of ["<AssistantPage />", "<ReportsPage />", "<AlertsPage />"]) {
  if (!app.includes(route)) throw new Error(`Inactive route: ${route}`);
}

const assistant = readFileSync(resolve(root, "src/pages/AssistantPage.tsx"), "utf8");
if (!assistant.includes("2xl:grid-cols-[235px_minmax(680px,1fr)_285px]")) {
  throw new Error("Expanded clinical chat layout is missing.");
}
if (!assistant.includes("clinical-message-text")) {
  throw new Error("Arabic-aware clinical message typography is missing.");
}

const viewer = readFileSync(resolve(root, "src/components/analysis/ImageReviewModal.tsx"), "utf8");
for (const marker of ["fetchAuthenticatedFile", "<img", "<svg", "downloadAnnotated"]) {
  if (!viewer.includes(marker)) throw new Error(`Simple clinical image viewer marker is missing: ${marker}`);
}

console.log("EyeAI Frontend Batch 04.2 verified successfully.");
