import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const backupPath = resolve(scriptDir, "anki-basic-template-backup-2026-05-06.json");

async function call(body) {
  const res = await fetch("http://127.0.0.1:8765", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();

  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`AnkiConnect returned non-JSON response: ${text}`);
  }

  if (!res.ok || payload.error) {
    throw new Error(payload.error || `AnkiConnect HTTP ${res.status}: ${text}`);
  }

  return payload.result;
}

const backup = JSON.parse(await readFile(backupPath, "utf8"));

if (!backup.modelName || typeof backup.css !== "string" || !backup.templates) {
  throw new Error(`Invalid Basic template backup: ${backupPath}`);
}

await call({
  action: "updateModelStyling",
  version: 6,
  params: { model: { name: backup.modelName, css: backup.css } },
});

await call({
  action: "updateModelTemplates",
  version: 6,
  params: { model: { name: backup.modelName, templates: backup.templates } },
});

console.log(`Restored ${backup.modelName} styling and templates from ${backupPath}`);
