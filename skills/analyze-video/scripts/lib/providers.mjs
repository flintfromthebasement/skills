/**
 * Provider helpers: Gemini Files API (recommended) + OpenAI fallback.
 *
 * API keys are read from the environment first, then from ~/.env
 * (simple KEY=value lines). Gemini accepts GEMINI_API_KEY,
 * GEMINI_PRO_API_KEY, or GOOGLE_API_KEY; OpenAI uses OPENAI_API_KEY.
 */

import { readFile, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const GEMINI_KEY_NAMES = ["GEMINI_API_KEY", "GEMINI_PRO_API_KEY", "GOOGLE_API_KEY"];
const OPENAI_KEY_NAMES = ["OPENAI_API_KEY"];

let envFileCache = null;

async function readEnvFile() {
  if (envFileCache) return envFileCache;
  envFileCache = {};
  const envPath = join(process.env.HOME || "", ".env");
  if (process.env.HOME && existsSync(envPath)) {
    const text = await readFile(envPath, "utf8");
    for (const line of text.split("\n")) {
      const m = line.match(/^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$/);
      if (!m) continue;
      let v = m[2].trim();
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
        v = v.slice(1, -1);
      }
      envFileCache[m[1]] = v;
    }
  }
  return envFileCache;
}

async function findKey(names) {
  for (const name of names) {
    if (process.env[name]) return process.env[name];
  }
  const fileVars = await readEnvFile();
  for (const name of names) {
    if (fileVars[name]) return fileVars[name];
  }
  return null;
}

export async function getGeminiKey({ required = true } = {}) {
  const key = await findKey(GEMINI_KEY_NAMES);
  if (!key && required) {
    throw new Error(`No Gemini API key found. Set one of ${GEMINI_KEY_NAMES.join(", ")} in the environment or ~/.env`);
  }
  return key;
}

export async function getOpenAIKey({ required = true } = {}) {
  const key = await findKey(OPENAI_KEY_NAMES);
  if (!key && required) {
    throw new Error("No OpenAI API key found. Set OPENAI_API_KEY in the environment or ~/.env");
  }
  return key;
}

/**
 * Picks a provider: explicit choice wins; otherwise Gemini if a key exists,
 * else OpenAI if a key exists. Returns { provider, note }.
 */
export async function resolveProvider(requested) {
  if (requested && requested !== "auto") {
    if (!["gemini", "openai"].includes(requested)) {
      throw new Error(`Unknown provider: ${requested} (expected gemini or openai)`);
    }
    return { provider: requested, note: null };
  }
  if (await getGeminiKey({ required: false })) return { provider: "gemini", note: null };
  if (await getOpenAIKey({ required: false })) {
    return {
      provider: "openai",
      note: "No Gemini key found — falling back to OpenAI. Gemini is recommended for audio/video analysis.",
    };
  }
  throw new Error(`No API key found. Set ${GEMINI_KEY_NAMES[0]} (recommended) or OPENAI_API_KEY in the environment or ~/.env`);
}

// ---------------------------------------------------------------------------
// Gemini Files API
// ---------------------------------------------------------------------------

const GEMINI_BASE = "https://generativelanguage.googleapis.com";

/**
 * Uploads a file via the resumable upload protocol (files up to 2GB).
 * Returns the file object ({ name, uri, state, ... }).
 */
export async function geminiUploadFile(filePath, mimeType, displayName) {
  const key = await getGeminiKey();
  const sizeBytes = (await stat(filePath)).size;

  const initRes = await fetch(`${GEMINI_BASE}/upload/v1beta/files?key=${key}`, {
    method: "POST",
    headers: {
      "X-Goog-Upload-Protocol": "resumable",
      "X-Goog-Upload-Command": "start",
      "X-Goog-Upload-Header-Content-Length": sizeBytes.toString(),
      "X-Goog-Upload-Header-Content-Type": mimeType,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ file: { displayName: displayName || filePath.split("/").pop() } }),
  });
  if (!initRes.ok) {
    throw new Error(`Gemini upload init failed (HTTP ${initRes.status}): ${await initRes.text()}`);
  }

  const uploadUrl = initRes.headers.get("x-goog-upload-url");
  if (!uploadUrl) throw new Error("Gemini upload init response missing x-goog-upload-url header.");

  const uploadRes = await fetch(uploadUrl, {
    method: "POST",
    headers: {
      "Content-Length": sizeBytes.toString(),
      "X-Goog-Upload-Offset": "0",
      "X-Goog-Upload-Command": "upload, finalize",
    },
    body: await readFile(filePath),
  });
  if (!uploadRes.ok) {
    throw new Error(`Gemini upload failed (HTTP ${uploadRes.status}): ${await uploadRes.text()}`);
  }
  return (await uploadRes.json()).file;
}

/** Polls until the uploaded file is ACTIVE (or throws on FAILED). */
export async function geminiPollFileState(fileName, onPoll = null, intervalMs = 5000) {
  const key = await getGeminiKey();
  while (true) {
    const res = await fetch(`${GEMINI_BASE}/v1beta/${fileName}?key=${key}`);
    if (!res.ok) {
      throw new Error(`Gemini file state check failed (HTTP ${res.status}): ${await res.text()}`);
    }
    const meta = await res.json();
    if (onPoll) onPoll(meta);
    if (meta.state === "ACTIVE") return meta;
    if (meta.state === "FAILED") {
      throw new Error(`Gemini file processing failed: ${JSON.stringify(meta.error || meta)}`);
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

/**
 * Generates content from an ordered parts array. Parts may be
 * { text } or { fileData: { fileUri, mimeType } }.
 */
export async function geminiGenerate(modelName, parts) {
  const key = await getGeminiKey();
  const res = await fetch(`${GEMINI_BASE}/v1beta/models/${modelName}:generateContent?key=${key}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contents: [{ parts }] }),
  });
  if (!res.ok) {
    throw new Error(`Gemini generateContent failed (HTTP ${res.status}): ${await res.text()}`);
  }
  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("\n").trim();
  if (!text) throw new Error(`Gemini returned no text: ${JSON.stringify(data)}`);
  return text;
}

/** Deletes an uploaded Gemini file. Returns false (with a warning) on failure. */
export async function geminiDeleteFile(fileName) {
  const key = await getGeminiKey();
  const res = await fetch(`${GEMINI_BASE}/v1beta/${fileName}?key=${key}`, { method: "DELETE" });
  if (!res.ok) {
    console.error(`Warning: failed to delete Gemini file ${fileName} (HTTP ${res.status}): ${await res.text()}`);
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// OpenAI (fallback)
// ---------------------------------------------------------------------------

const OPENAI_BASE = "https://api.openai.com/v1";

/**
 * Chat completion with arbitrary content parts (text, input_audio, image_url).
 * Returns the assistant message text.
 */
export async function openaiChat(model, contentParts, systemText = null) {
  const key = await getOpenAIKey();
  const messages = [];
  if (systemText) messages.push({ role: "system", content: systemText });
  messages.push({ role: "user", content: contentParts });
  const body = { model, messages };
  // Audio models require modalities; text/vision models reject the parameter.
  if (contentParts.some((p) => p.type === "input_audio")) body.modalities = ["text"];

  let res = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    res = await fetch(`${OPENAI_BASE}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify(body),
    });
    if (res.ok) break;
    const errText = await res.text();
    // 5xx (incl. transient "model produced invalid content") and 429 are retryable
    if ((res.status >= 500 || res.status === 429) && attempt < 3) {
      console.error(`[openai] HTTP ${res.status}, retrying (${attempt}/3)`);
      await new Promise((r) => setTimeout(r, 2000 * attempt));
      continue;
    }
    throw new Error(`OpenAI chat completion failed (HTTP ${res.status}): ${errText}`);
  }
  const data = await res.json();
  const msg = data.choices?.[0]?.message;
  const text = (msg?.content || msg?.audio?.transcript || "").trim();
  if (!text) throw new Error(`OpenAI returned no text: ${JSON.stringify(data)}`);
  return text;
}

/**
 * Transcribes an audio file via /v1/audio/transcriptions.
 * File must be <= 25MB (API limit). Returns transcript text.
 */
export async function openaiTranscribe(filePath, model = "gpt-4o-mini-transcribe") {
  const key = await getOpenAIKey();
  const sizeBytes = (await stat(filePath)).size;
  if (sizeBytes > 25 * 1024 * 1024) {
    throw new Error(`Audio file is ${(sizeBytes / 1024 / 1024).toFixed(1)}MB; the transcription API limit is 25MB.`);
  }
  const form = new FormData();
  const bytes = await readFile(filePath);
  form.append("file", new Blob([bytes]), filePath.split("/").pop());
  form.append("model", model);
  const res = await fetch(`${OPENAI_BASE}/audio/transcriptions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
    body: form,
  });
  if (!res.ok) {
    throw new Error(`OpenAI transcription failed (HTTP ${res.status}): ${await res.text()}`);
  }
  const data = await res.json();
  return (data.text || "").trim();
}
