#!/usr/bin/env node
/**
 * audio-analysis runner
 *
 * Listens to audio with a multimodal model and writes a practical analysis.
 * Gemini (Files API) is the recommended provider; OpenAI audio-input chat
 * completions are the fallback. ffmpeg/ffprobe render metadata and
 * waveform/spectrogram artifacts; yt-dlp handles YouTube audio.
 */

import { existsSync } from "node:fs";
import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { basename, extname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import {
  resolveProvider,
  geminiUploadFile,
  geminiPollFileState,
  geminiGenerate,
  geminiDeleteFile,
  openaiChat,
} from "./lib/providers.mjs";

const execFileP = promisify(execFile);

const DEFAULT_MODELS = {
  gemini: "gemini-2.5-flash",
  openai: "gpt-audio-1.5",
};

const AUDIO_MIME_TYPES = new Map([
  [".aac", "audio/aac"],
  [".aif", "audio/aiff"],
  [".aiff", "audio/aiff"],
  [".flac", "audio/flac"],
  [".m4a", "audio/mp4"],
  [".mp3", "audio/mp3"],
  [".oga", "audio/ogg"],
  [".ogg", "audio/ogg"],
  [".opus", "audio/ogg"],
  [".wav", "audio/wav"],
  [".weba", "audio/webm"],
  [".webm", "audio/webm"],
]);

const GENERAL_PROMPT = `You are analyzing an audio file. Listen to the full recording and answer with a direct, useful assessment.

If this is music, cover:
- Vocals: number/type of voices, delivery, harmonies, effects, lyric snippets if identifiable.
- Instrumentation: specific instruments, arrangement density, rhythm, tempo feel, texture.
- Structure: intro/verse/chorus/bridge/drop/breakdown shape, dynamics, builds, where it breathes.
- Mix/production: balance, stereo field, artifacts, abrupt transitions, AI-isms, polish.
- Vibe: concise emotional/creative read.

If this is not music, identify what the sound likely is, describe the acoustic evidence, and note uncertainty.

Be specific, practical, and concise.`;

const SUNO_PROMPT = `You are a thoughtful, creative music collaborator and producer with an excellent ear for vibe, structure, and instrumentation.
Analyze this track so we can generate Suno prompts that capture the style without copying artist or song names.

Structure your response into exactly three sections:

# LYRICS & VOCALS
Analyze vocal style, likely gender/tone if discernible, delivery, harmonies, effects/layering, and key lyric snippets if identifiable.

# PRODUCTION & INSTRUMENTATION
Analyze active instruments, arrangement density, song structure, tempo feel, dynamics, builds/drops, and sonic texture.

# SUNO STYLE PROMPT
Generate a production-ready Suno prompt under 1000 characters.
Rules:
- Do NOT mention artist, band, or song names.
- Use direct descriptors: genres, sub-genres, eras, instruments, vocal descriptions, energy/mood arc, and mix texture.
- Prefer comma-separated tags and concise evocative phrases.
- Put only the final prompt text inside a markdown code block.`;

const COMPARE_PROMPT = `You are hearing multiple audio files. Analyze each one briefly, then compare the meaningful differences in performance, arrangement, mix, energy, and usefulness as a reference.

Do not pick a winner unless the user explicitly asks. Present the tradeoffs clearly.`;

function parseArgs(argv) {
  const args = {
    files: [],
    urls: [],
    compare: false,
    mode: "general",
    prompt: null,
    out: null,
    provider: "auto",
    model: null,
    json: false,
    noVisuals: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--file") args.files.push(argv[++i]);
    else if (a === "--url") args.urls.push(argv[++i]);
    else if (a === "--compare") args.compare = true;
    else if (a === "--mode") args.mode = argv[++i];
    else if (a === "--prompt") args.prompt = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--provider") args.provider = argv[++i];
    else if (a === "--model") args.model = argv[++i];
    else if (a === "--json") args.json = true;
    else if (a === "--no-visuals") args.noVisuals = true;
    else if (a === "--transcribe") {
      args.prompt = appendPrompt(args.prompt, "Also include a transcript or best-effort lyric transcription if the speech or lyrics are intelligible.");
    } else if (a === "--help" || a === "-h") {
      printHelp();
      process.exit(0);
    } else {
      console.error(`Unknown arg: ${a}`);
      process.exit(2);
    }
  }

  if (!["general", "suno"].includes(args.mode)) {
    console.error(`ERROR: --mode must be "general" or "suno"`);
    process.exit(2);
  }

  return args;
}

function printHelp() {
  console.log(`Usage: run.mjs --file <path> [--file <path>...] [--url <youtube-url-or-id>...]
                [--mode general|suno] [--prompt <question>] [--compare]
                [--out <dir>] [--provider auto|gemini|openai] [--model <model>]
                [--json] [--no-visuals]

Providers:
  gemini (recommended, default when GEMINI_API_KEY is set) — native long-audio understanding
  openai (fallback) — audio-input chat completions (gpt-audio-1.5 by default)

Examples:
  run.mjs --file song.mp3
  run.mjs --url "https://www.youtube.com/watch?v=VIDEO_ID" --mode suno
  run.mjs --file sound.wav --prompt "What animal is this?"
  run.mjs --file v1.mp3 --file v2.mp3 --compare
  run.mjs --file song.mp3 --provider openai`);
}

function appendPrompt(base, extra) {
  return base ? `${base}\n\n${extra}` : extra;
}

function buildPrompt(args, inputCount) {
  const base = args.mode === "suno" ? SUNO_PROMPT : GENERAL_PROMPT;
  const comparison = args.compare || inputCount > 1 ? `\n\n${COMPARE_PROMPT}` : "";
  const custom = args.prompt ? `\n\nUser's specific question or focus:\n${args.prompt}` : "";
  return `${base}${comparison}${custom}`.trim();
}

function mimeForFile(path) {
  const ext = extname(path).toLowerCase();
  return AUDIO_MIME_TYPES.get(ext) || "audio/mpeg";
}

function looksLikePlaceholderPath(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
  return [
    "attached mp3",
    "attached audio",
    "the mp3",
    "the audio",
    "this mp3",
    "this audio",
    "audio file",
    "mp3 file",
  ].includes(normalized);
}

function formatDuration(seconds) {
  if (!seconds || Number.isNaN(seconds)) return "?";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatSize(bytes) {
  if (!bytes) return "?";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

async function ffprobeFile(path) {
  try {
    const { stdout } = await execFileP("ffprobe", [
      "-v", "error",
      "-show_format",
      "-show_streams",
      "-of", "json",
      path,
    ]);
    const data = JSON.parse(stdout);
    const audioStream = (data.streams || []).find((s) => s.codec_type === "audio");
    return {
      duration: parseFloat(data.format?.duration || audioStream?.duration || 0),
      bitrate: parseInt(data.format?.bit_rate || audioStream?.bit_rate || 0, 10),
      sampleRate: parseInt(audioStream?.sample_rate || 0, 10),
      channels: audioStream?.channels || null,
      codec: audioStream?.codec_name || null,
      sizeBytes: parseInt(data.format?.size || 0, 10),
    };
  } catch (err) {
    return { error: err.message };
  }
}

async function renderWaveform(inPath, outPath) {
  await execFileP("ffmpeg", [
    "-y", "-i", inPath,
    "-filter_complex", "showwavespic=s=1200x300:colors=#3b9eef",
    outPath,
  ]);
}

async function renderSpectrogram(inPath, outPath) {
  await execFileP("ffmpeg", [
    "-y", "-i", inPath,
    "-lavfi", "showspectrumpic=s=1200x500:legend=1:mode=combined:color=intensity",
    outPath,
  ]);
}

async function downloadYoutubeAudio(url, outDir) {
  console.error(`[youtube] Fetching title for ${url}`);
  const { stdout: titleOut } = await execFileP("yt-dlp", ["--print", "title", url]);
  const title = titleOut.trim() || "YouTube audio";
  const tempFilePattern = join(outDir, `yt-audio-${Date.now()}.%(ext)s`);

  console.error(`[youtube] Downloading audio: ${title}`);
  await execFileP("yt-dlp", [
    "-x",
    "--audio-format", "mp3",
    "--audio-quality", "5",
    "-o", tempFilePattern,
    url,
  ]);

  const { stdout: filesList } = await execFileP("find", [
    outDir, "-maxdepth", "1", "-name", "yt-audio-*",
  ]);
  const paths = filesList.trim().split("\n").filter(Boolean).sort();
  if (paths.length === 0) {
    throw new Error("Failed to locate downloaded YouTube audio file.");
  }

  return { path: paths[paths.length - 1], title, isTempFile: true };
}

async function prepareInputs(args, workDir) {
  const inputs = args.files.map((filePath) => {
    if (looksLikePlaceholderPath(filePath)) {
      throw new Error(`--file is a placeholder (${filePath}), not a real audio file path. Re-run with the actual file path or a URL.`);
    }
    return { path: resolve(filePath), title: basename(filePath), isTempFile: false };
  });

  for (const url of args.urls) {
    inputs.push(await downloadYoutubeAudio(url, workDir));
  }

  return inputs;
}

async function renderVisuals(input, outDir) {
  const slug = basename(input.path).replace(/[^a-z0-9._-]/gi, "_");
  const waveform = join(outDir, `${slug}.waveform.png`);
  const spectrogram = join(outDir, `${slug}.spectrogram.png`);
  const result = { waveform: null, spectrogram: null };

  try {
    await renderWaveform(input.path, waveform);
    result.waveform = waveform;
  } catch (err) {
    console.error(`  [waveform] failed for ${basename(input.path)}: ${err.message}`);
  }

  try {
    await renderSpectrogram(input.path, spectrogram);
    result.spectrogram = spectrogram;
  } catch (err) {
    console.error(`  [spectrogram] failed for ${basename(input.path)}: ${err.message}`);
  }

  return result;
}

// --- Gemini path ---

async function analyzeWithGemini(model, inputs, prompt) {
  const uploaded = [];
  try {
    for (const input of inputs) {
      const mimeType = mimeForFile(input.path);
      const displayName = input.title || basename(input.path);
      console.error(`[gemini] Uploading ${displayName} (${mimeType})`);
      const fileMeta = await geminiUploadFile(input.path, mimeType, displayName);
      await geminiPollFileState(fileMeta.name, (m) => {
        console.error(`  [gemini] ${displayName}: ${m.state}`);
      });
      uploaded.push({ ...input, mimeType, fileMeta });
    }

    const parts = [];
    for (const item of uploaded) {
      if (uploaded.length > 1) parts.push({ text: `Audio file: ${item.title || basename(item.path)}` });
      parts.push({ fileData: { fileUri: item.fileMeta.uri, mimeType: item.mimeType } });
    }
    parts.push({ text: prompt });

    console.error(`[gemini] Analysis starting using ${model}`);
    return await geminiGenerate(model, parts);
  } finally {
    await Promise.allSettled(uploaded.map((item) =>
      item.fileMeta?.name ? geminiDeleteFile(item.fileMeta.name) : Promise.resolve()
    ));
  }
}

// --- OpenAI path ---

const OPENAI_NATIVE_FORMATS = new Set([".wav", ".mp3"]);
const OPENAI_MAX_AUDIO_BYTES = 20 * 1024 * 1024;

async function toOpenAIAudio(input, workDir) {
  let path = input.path;
  let format = extname(path).toLowerCase().slice(1);
  if (!OPENAI_NATIVE_FORMATS.has(extname(path).toLowerCase())) {
    const converted = join(workDir, `${basename(path).replace(/[^a-z0-9._-]/gi, "_")}.mp3`);
    console.error(`[openai] Transcoding ${basename(path)} to mp3 (OpenAI accepts wav/mp3 input)`);
    await execFileP("ffmpeg", ["-y", "-i", path, "-b:a", "128k", converted]);
    path = converted;
    format = "mp3";
  }
  const sizeBytes = (await stat(path)).size;
  if (sizeBytes > OPENAI_MAX_AUDIO_BYTES) {
    throw new Error(`${basename(input.path)} is ${formatSize(sizeBytes)} after encoding — too large for inline OpenAI audio input (~20MB). Use --provider gemini for long audio.`);
  }
  const data = (await readFile(path)).toString("base64");
  return { type: "input_audio", input_audio: { data, format } };
}

/**
 * gpt-audio-1.5 intermittently wraps output in arbitrary JSON (sometimes
 * contentless meta like {"hearing": "request"}). Detect that, retry, and on
 * the last attempt salvage any real prose from the JSON string values.
 */
function extractJunkJson(text) {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function salvageProse(value, out = []) {
  if (typeof value === "string") {
    if (value.length >= 60) out.push(value);
  } else if (Array.isArray(value)) {
    value.forEach((v) => salvageProse(v, out));
  } else if (value && typeof value === "object") {
    Object.values(value).forEach((v) => salvageProse(v, out));
  }
  return out;
}

async function analyzeWithOpenAI(model, inputs, prompt, workDir) {
  const parts = [];
  for (const input of inputs) {
    if (inputs.length > 1) parts.push({ type: "text", text: `Audio file: ${input.title || basename(input.path)}` });
    parts.push(await toOpenAIAudio(input, workDir));
  }
  parts.push({ type: "text", text: prompt });
  console.error(`[openai] Analysis starting using ${model}`);

  const attempts = 3;
  let lastText = null;
  for (let i = 1; i <= attempts; i++) {
    const text = await openaiChat(model, parts, "You analyze audio. Respond in plain markdown prose, never JSON.");
    const junk = extractJunkJson(text);
    if (!junk) return text;
    lastText = text;
    const prose = salvageProse(junk);
    if (prose.length > 0 && i === attempts) return prose.join("\n\n");
    console.error(`[openai] Attempt ${i}/${attempts} returned JSON instead of prose — ${i < attempts ? "retrying" : "salvaging"}`);
  }
  const prose = salvageProse(extractJunkJson(lastText) || {});
  return prose.length > 0 ? prose.join("\n\n") : lastText;
}

// --- Output ---

function inputSummary(input, ffmeta, visuals) {
  return {
    path: input.path,
    title: input.title,
    mimeType: mimeForFile(input.path),
    ffmeta,
    waveform: visuals?.waveform || null,
    spectrogram: visuals?.spectrogram || null,
  };
}

function buildMarkdown({ ts, outDir, provider, model, mode, prompt, files, analysis }) {
  const lines = [];
  lines.push(`# Audio analysis - ${ts}\n`);
  lines.push(`Output: \`${outDir}\``);
  lines.push(`Provider: \`${provider}\` - Model: \`${model}\``);
  lines.push(`Mode: \`${mode}\``);
  if (prompt) lines.push(`Prompt: ${prompt}`);
  lines.push("");

  for (const file of files) {
    lines.push(`## ${file.title || basename(file.path)}`);
    const meta = file.ffmeta;
    if (meta && !meta.error) {
      lines.push(
        `- Duration: ${formatDuration(meta.duration)} - Bitrate: ${
          meta.bitrate ? `${Math.round(meta.bitrate / 1000)} kbps` : "?"
        } - ${meta.channels || "?"}ch ${meta.sampleRate || "?"}Hz - ${formatSize(meta.sizeBytes)}`
      );
      if (meta.codec) lines.push(`- Codec: ${meta.codec}`);
    } else if (meta?.error) {
      lines.push(`- ffprobe error: ${meta.error}`);
    }
    if (file.waveform) lines.push(`- Waveform: \`${file.waveform}\``);
    if (file.spectrogram) lines.push(`- Spectrogram: \`${file.spectrogram}\``);
    lines.push("");
  }

  lines.push("## Analysis\n");
  lines.push(analysis);
  lines.push("");

  return lines.join("\n");
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.files.length === 0 && args.urls.length === 0) {
    console.error("ERROR: provide at least one --file or --url");
    process.exit(2);
  }

  const { provider, note } = await resolveProvider(args.provider);
  if (note) console.error(`[provider] ${note}`);
  const model = args.model || DEFAULT_MODELS[provider];

  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const outDir = args.out ? resolve(args.out) : resolve(`audio-analysis-output/${ts}`);
  const workDir = join(tmpdir(), `audio-analysis-${Date.now()}`);
  await mkdir(outDir, { recursive: true });
  await mkdir(workDir, { recursive: true });

  let inputs = [];

  try {
    inputs = await prepareInputs(args, workDir);
    for (const input of inputs) {
      if (!existsSync(input.path)) {
        throw new Error(`File not found: ${input.path}`);
      }
    }

    const files = [];
    for (const input of inputs) {
      const ffmeta = await ffprobeFile(input.path);
      const visuals = args.noVisuals ? null : await renderVisuals(input, outDir);
      files.push(inputSummary(input, ffmeta, visuals));
    }

    const prompt = buildPrompt(args, inputs.length);
    const analysis = provider === "gemini"
      ? await analyzeWithGemini(model, inputs, prompt)
      : await analyzeWithOpenAI(model, inputs, prompt, workDir);

    const manifest = {
      timestamp: ts,
      outDir,
      provider,
      model,
      mode: args.mode,
      compare: args.compare || inputs.length > 1,
      prompt: args.prompt,
      files,
      analysis,
    };
    await writeFile(join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));

    if (args.json) {
      console.log(JSON.stringify(manifest, null, 2));
    } else {
      const md = buildMarkdown({
        ts, outDir, provider, model,
        mode: args.mode,
        prompt: args.prompt,
        files, analysis,
      });
      await writeFile(join(outDir, "summary.md"), md);
      console.log(md);
    }
  } catch (err) {
    console.error("FATAL:", err.stack || err.message);
    process.exitCode = 1;
  } finally {
    for (const input of inputs) {
      if (input.isTempFile && input.path && existsSync(input.path)) {
        await rm(input.path, { force: true }).catch(() => {});
      }
    }
    await rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

main();
