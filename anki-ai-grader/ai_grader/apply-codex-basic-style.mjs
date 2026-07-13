const css = `.card {
  margin: 0;
  padding: 0;
  background: #ffffff;
  color: #111111;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Arial, sans-serif;
  font-size: 17px;
  line-height: 1.42;
  text-align: center;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

html,
body {
  margin: 0 !important;
  padding: 0 !important;
  width: 100% !important;
  background: #ffffff !important;
}

#qa {
  box-sizing: border-box;
  width: 100% !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 86px 0 178px !important;
}

.codex-shell {
  box-sizing: border-box;
  width: min(100% - 220px, 780px);
  min-height: 0 !important;
  margin: 0 auto !important;
  padding: 0 !important;
}

.codex-question {
  font-size: 21px !important;
  font-weight: 400 !important;
  line-height: 1.34;
  letter-spacing: 0;
  max-width: 780px !important;
  margin: 0 auto !important;
  text-align: center !important;
}

#qa .codex-tags,
#qa .codex-tag-pill {
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  overflow: hidden !important;
}

#ai-grader-answer-wrap,
.ai-grader-answer-wrap {
  box-sizing: border-box;
  position: fixed !important;
  left: 50% !important;
  right: auto !important;
  bottom: 58px !important;
  transform: translateX(-50%) !important;
  z-index: 20 !important;
  width: min(100% - 220px, 780px) !important;
  max-width: 780px !important;
  margin: 0 !important;
  padding: 0 !important;
}

#ai-grader-symbols-root {
  display: flex !important;
  flex-direction: column !important;
  align-items: stretch !important;
}

#ai-grader-symbols-root > summary {
  align-self: flex-start !important;
  order: 2 !important;
}

#ai-grader-symbol-groups {
  box-sizing: border-box !important;
  order: 1 !important;
  width: 100% !important;
  max-height: min(42vh, 400px) !important;
  overflow-y: auto !important;
  overscroll-behavior: contain;
}

#ai-grader-answer,
.ai-grader-answer {
  box-sizing: border-box !important;
  display: block !important;
  width: 100% !important;
  height: 124px !important;
  min-height: 124px !important;
  max-height: 124px !important;
  border: 1px solid #dedede !important;
  border-radius: 20px !important;
  background: #ffffff !important;
  color: #111111 !important;
  padding: 24px 28px !important;
  font: 19px/1.4 -apple-system, BlinkMacSystemFont, "SF Pro Text", Arial, sans-serif !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .03) !important;
  outline: none !important;
  resize: none !important;
  overflow: auto !important;
}

#ai-grader-answer::placeholder,
.ai-grader-answer::placeholder {
  color: #bdbdbd !important;
  opacity: 1 !important;
}

.codex-answer-wrap {
  max-width: 780px !important;
  margin: 50px auto 0 !important;
}

.codex-answer {
  border-left: 0;
  padding-left: 0;
  color: #111111;
  font-size: 22px;
  font-style: italic;
  font-weight: 400;
  line-height: 1.48;
  text-align: center;
}

.codex-type-answer {
  max-width: 780px !important;
  margin: 50px auto 0 !important;
  color: #111111;
  font-size: 19px;
  line-height: 1.45;
  text-align: center;
}

.codex-answer img {
  max-width: min(100%, 420px);
  height: auto;
  border-radius: 6px;
}

.codex-divider,
hr#answer {
  display: none;
}

@media (max-width: 720px) {
  #qa {
    padding: 42px 0 184px !important;
  }

  .codex-shell {
    width: min(100% - 48px, 920px);
  }

  .codex-question {
    font-size: 21px;
  }

  #ai-grader-answer-wrap,
  .ai-grader-answer-wrap {
    bottom: 42px !important;
    width: min(100% - 48px, 920px) !important;
  }

  #ai-grader-answer,
  .ai-grader-answer {
    height: 124px !important;
    min-height: 124px !important;
    max-height: 124px !important;
    font-size: 18px !important;
  }

  .codex-answer-wrap {
    margin-top: 42px !important;
  }

  .codex-type-answer {
    margin-top: 42px !important;
  }
}
`;

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

function fieldSet(fields) {
  return new Set(fields.map((field) => String(field).trim().toLowerCase()));
}

function compatibleFrontBackFields(fields) {
  const names = fieldSet(fields);
  return names.has("front") && names.has("back");
}

function isReverseTemplate(template) {
  const front = String(template?.Front || "");
  return /\{\{\s*Back\s*\}\}/.test(front) && !/\{\{\s*Front\s*\}\}/.test(front);
}

function hasTypeAnswerTemplate(template) {
  return /\{\{\s*type\s*:\s*Back\s*\}\}/i.test(
    `${String(template?.Front || "")}\n${String(template?.Back || "")}`,
  );
}

function hasOptionalReverseTemplate(template) {
  return /\{\{[#/^]\s*Add Reverse\s*\}\}/.test(
    `${String(template?.Front || "")}\n${String(template?.Back || "")}`,
  );
}

function styledTemplate(questionField, answerField) {
  return {
    Front: `<div class="codex-shell">
  <div class="codex-question">{{${questionField}}}</div>
</div>`,
    Back: `<div class="codex-shell">
  <div class="codex-question">{{${questionField}}}</div>
  <div class="codex-answer-wrap">
    <div class="codex-answer">{{${answerField}}}</div>
  </div>
</div>`,
  };
}

function styledTypeAnswerTemplate() {
  return {
    Front: `<div class="codex-shell">
  <div class="codex-question">{{Front}}</div>
  <div class="codex-type-answer">{{type:Back}}</div>
</div>`,
    Back: `<div class="codex-shell">
  <div class="codex-question">{{Front}}</div>
  <div class="codex-answer-wrap">
    <div class="codex-answer">{{type:Back}}</div>
  </div>
</div>`,
  };
}

function styledOptionalReverseTemplate() {
  return {
    Front: `<div class="codex-shell">
  {{#Add Reverse}}<div class="codex-question">{{Back}}</div>{{/Add Reverse}}
</div>`,
    Back: `<div class="codex-shell">
  {{#Add Reverse}}<div class="codex-question">{{Back}}</div>
  <div class="codex-answer-wrap">
    <div class="codex-answer">{{Front}}</div>
  </div>{{/Add Reverse}}
</div>`,
  };
}

function styledTemplates(modelName, existingTemplates) {
  const isTypeAnswerModel = /type in the answer/i.test(modelName);
  const isOptionalReverseModel = /optional reversed card/i.test(modelName);

  return Object.fromEntries(
    Object.entries(existingTemplates).map(([name, template], index) => {
      if (isTypeAnswerModel || hasTypeAnswerTemplate(template)) {
        return [name, styledTypeAnswerTemplate()];
      }

      if (hasOptionalReverseTemplate(template) || (isOptionalReverseModel && index === 1)) {
        return [name, styledOptionalReverseTemplate()];
      }

      const reverse = isReverseTemplate(template);
      return [name, styledTemplate(reverse ? "Back" : "Front", reverse ? "Front" : "Back")];
    }),
  );
}

const modelNames = await call({ action: "modelNames", version: 6 });
const updatedModels = [];
const skippedModels = [];

for (const modelName of modelNames) {
  const fields = await call({
    action: "modelFieldNames",
    version: 6,
    params: { modelName },
  });

  if (!compatibleFrontBackFields(fields)) {
    skippedModels.push(modelName);
    continue;
  }

  const existingTemplates = await call({
    action: "modelTemplates",
    version: 6,
    params: { modelName },
  });

  await call({
    action: "updateModelStyling",
    version: 6,
    params: { model: { name: modelName, css } },
  });

  await call({
    action: "updateModelTemplates",
    version: 6,
    params: { model: { name: modelName, templates: styledTemplates(modelName, existingTemplates) } },
  });

  updatedModels.push(modelName);
}

console.log(`Updated ${updatedModels.length} Front/Back note type(s):`);
for (const modelName of updatedModels) {
  console.log(`- ${modelName}`);
}

if (skippedModels.length) {
  console.log(`Skipped ${skippedModels.length} note type(s) without Front and Back fields.`);
}
