#!/usr/bin/env node
/**
 * analyze-video runner
 *
 * Multimodal video analysis. Gemini (Files API) is the recommended provider —
 * it watches the actual video natively (frames + audio, up to ~2GB uploads).
 * The OpenAI fallback approximates this by sampling frames with ffmpeg,
 * transcribing the audio track, and sending both to a vision model.
 * yt-dlp handles YouTube URLs.
 */

import { existsSync } from "node:fs";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
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
  openaiTranscribe,
} from "./lib/providers.mjs";

const execFileP = promisify(execFile);

const DEFAULT_MODELS = {
  gemini: "gemini-2.5-pro",
  openai: "gpt-5.5",
};

const VIDEO_MIME_TYPES = new Map([
  [".3gp", "video/3gpp"],
  [".avi", "video/x-msvideo"],
  [".flv", "video/x-flv"],
  [".m4v", "video/mp4"],
  [".mkv", "video/x-matroska"],
  [".mov", "video/quicktime"],
  [".mp4", "video/mp4"],
  [".mpeg", "video/mpeg"],
  [".mpg", "video/mpeg"],
  [".webm", "video/webm"],
]);

const MODE_PROMPTS = {
  summary: `Analyze this video using both the visual frames and the audio. Give a concise but useful summary:

# SUMMARY
What the video is about, its likely purpose, audience, tone, and central takeaways.

# IMPORTANT VISUAL DETAILS
Describe the visible scenes, screen content, slides, UI, objects, actions, text, and visual evidence that would be missed by transcript-only reading.

# NOTABLE MOMENTS
Use timestamps where possible for important visual/audio moments.

# PRACTICAL READ
End with the most useful interpretation, caveats, or next-step advice.`,

  visual: `Analyze what is visible in this video. Prioritize frame-level evidence over transcript-style summary:

# VISUAL ANSWER
Directly answer what is shown and what appears to be happening.

# TIMELINE OF VISIBLE EVENTS
Use timestamps where possible. Describe scenes, people, objects, slides, UI, screen text, motion, gestures, and changes.

# EVIDENCE & UNCERTAINTY
Call out what is clear, what is inferred, and what cannot be determined from the frames.`,

  production: `Analyze this video as a production/style reference:

# PRODUCTION SUMMARY
Overall format, genre, audience, pacing, and creative intent.

# VISUAL STYLE
Camera/framing, lighting, color, graphics, typography, visual transitions, screen design, set/location, and composition.

# EDITING & SOUND
Editing rhythm, music, voice, sound design, cuts, structure, hooks, and retention tactics.

# REPRODUCTION NOTES
Practical notes for creating a similar video without copying any specific creator.`,

  deep: `Analyze the provided video in its entirety using visual frames and audio:

# EXECUTIVE SUMMARY
A high-level summary of the video's purpose, central thesis, audience, and overall tone.

# TIMESTAMPED CHAPTERS & SCENES
Provide a detailed timeline. For each segment, describe what is discussed and what is visibly shown: slides, screen shares, whiteboards, code editors, UI, physical items, facial expressions, gestures, text on screen, camera focus, and scene changes.

# CORE LESSONS & TAKEAWAYS
The most important insights, arguments, or practical lessons.

# VISUAL & PRODUCTION DNA
Editing pace, framing, lighting, sound design, color palette, on-screen graphics, structure, and overall quality.

Highlight details in the visuals that a plain audio transcript would miss.`,
};

function parseArgs(argv) {
  const args = {
    file: null,
    url: null,
    mode: "summary",
    prompt: null,
    out: null,
    provider: "auto",
    model: null,
    maxFrames: 20,
    json: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--file") args.file = argv[++i];
    else if (a === "--url") args.url = argv[++i];
    else if (a === "--mode") args.mode = argv[++i];
    else if (a === "--prompt") args.prompt = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--provider") args.provider = argv[++i];
    else if (a === "--model") args.model = argv[++i];
    else if (a === "--max-frames") args.maxFrames = parseInt(argv[++i], 10);
    else if (a === "--json") args.json = true;
    else if (a === "--help" || a === "-h") {
      printHelp();
      process.exit(0);
    } else {
      console.error(`Unknown arg: ${a}`);
      process.exit(2);
    }
  }

  if (!Object.hasOwn(MODE_PROMPTS, args.mode)) {
    console.error(`ERROR: --mode must be one of: ${Object.keys(MODE_PROMPTS).join(", ")}`);
    process.exit(2);
  }
  if (!Number.isInteger(args.maxFrames) || args.maxFrames < 1 || args.maxFrames > 50) {
    console.error("ERROR: --max-frames must be an integer between 1 and 50");
    process.exit(2);
  }

  return args;
}

function printHelp() {
  console.log(`Usage: run.mjs (--file <path> | --url <youtube-url-or-id>)
                [--mode summary|visual|production|deep] [--prompt <question>]
                [--out <dir>] [--provider auto|gemini|openai] [--model <model>]
                [--max-frames <n>] [--json]

Providers:
  gemini (recommended, default when GEMINI_API_KEY is set) — watches the actual
    video natively, frames + audio together
  openai (fallback) — samples up to --max-frames frames + transcribes the audio
    track, then analyzes with a vision model (gpt-5.5 by default)

Examples:
  run.mjs --url "https://www.youtube.com/watch?v=VIDEO_ID"
  run.mjs --url "https://www.youtube.com/watch?v=VIDEO_ID" --mode visual --prompt "What is shown on screen?"
  run.mjs --file demo.mp4 --mode production
  run.mjs --file demo.mp4 --provider openai --max-frames 30`);
}

function buildPrompt(args) {
  const base = MODE_PROMPTS[args.mode];
  const custom = args.prompt ? `\n\nUser's specific question or focus:\n${args.prompt}` : "";
  return `${base}${custom}`.trim();
}

function mimeForFile(path) {
  return VIDEO_MIME_TYPES.get(extname(path).toLowerCase()) || "video/mp4";
}

function looksLikePlaceholderPath(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
  return [
    "attached video",
    "attached mp4",
    "the video",
    "this video",
    "video file",
    "mp4 file",
    "attached file",
  ].includes(normalized);
}

function formatDuration(seconds) {
  if (!seconds || Number.isNaN(seconds)) return "?";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h > 0
    ? `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
    : `${m}:${s.toString().padStart(2, "0")}`;
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
    const videoStream = (data.streams || []).find((s) => s.codec_type === "video");
    const audioStream = (data.streams || []).find((s) => s.codec_type === "audio");
    return {
      duration: parseFloat(data.format?.duration || videoStream?.duration || 0),
      sizeBytes: parseInt(data.format?.size || 0, 10),
      bitrate: parseInt(data.format?.bit_rate || videoStream?.bit_rate || 0, 10),
      videoCodec: videoStream?.codec_name || null,
      audioCodec: audioStream?.codec_name || null,
      width: videoStream?.width || null,
      height: videoStream?.height || null,
      frameRate: videoStream?.avg_frame_rate || null,
    };
  } catch (err) {
    return { error: err.message };
  }
}

function normalizeYoutubeUrl(value) {
  if (/^https?:\/\//i.test(value)) return value;
  return `https://www.youtube.com/watch?v=${value}`;
}

async function downloadYoutubeVideo(url, outDir) {
  const normalizedUrl = normalizeYoutubeUrl(url);
  console.error(`[youtube] Fetching title for ${normalizedUrl}`);
  const { stdout: titleOut } = await execFileP("yt-dlp", ["--print", "title", normalizedUrl]);
  const title = titleOut.trim() || "YouTube video";
  const tempFilePattern = join(outDir, `yt-video-${Date.now()}.%(ext)s`);

  console.error(`[youtube] Downloading lightweight 480p MP4: ${title}`);
  await execFileP("yt-dlp", [
    "-f",
    "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/best",
    "--merge-output-format", "mp4",
    "-o", tempFilePattern,
    normalizedUrl,
  ]);

  const { stdout: filesList } = await execFileP("find", [
    outDir, "-maxdepth", "1", "-name", "yt-video-*",
  ]);
  const paths = filesList.trim().split("\n").filter(Boolean).sort();
  if (paths.length === 0) {
    throw new Error("Failed to locate downloaded YouTube video file.");
  }

  return { path: paths[paths.length - 1], title, sourceUrl: normalizedUrl, isTempFile: true };
}

async function prepareInput(args, workDir) {
  if (args.file && args.url) {
    throw new Error("Provide either --file or --url, not both.");
  }

  if (args.url) return downloadYoutubeVideo(args.url, workDir);

  if (looksLikePlaceholderPath(args.file)) {
    throw new Error(`--file is a placeholder (${args.file}), not a real video file path. Re-run with the actual file path or a URL.`);
  }

  const filePath = resolve(args.file);
  if (!existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }

  return { path: filePath, title: basename(filePath), sourceUrl: null, isTempFile: false };
}

// --- Gemini path ---

async function analyzeWithGemini(model, input, mimeType, prompt) {
  let uploaded = null;
  try {
    console.error(`[gemini] Uploading ${input.title || basename(input.path)} (${mimeType})`);
    uploaded = await geminiUploadFile(input.path, mimeType, input.title || basename(input.path));
    console.error(`[gemini] Uploaded as ${uploaded.name}`);
    await geminiPollFileState(uploaded.name, (m) => {
      console.error(`  [gemini] ${m.state}`);
    });

    console.error(`[gemini] Video analysis starting using ${model}`);
    return await geminiGenerate(model, [
      { fileData: { fileUri: uploaded.uri, mimeType } },
      { text: prompt },
    ]);
  } finally {
    if (uploaded?.name) await geminiDeleteFile(uploaded.name).catch(() => {});
  }
}

// --- OpenAI path (frame sampling + transcript) ---

async function extractFrames(input, duration, maxFrames, workDir) {
  const frames = [];
  const count = duration > 0 ? Math.min(maxFrames, Math.max(4, Math.ceil(duration / 10))) : maxFrames;
  const usable = Math.max(duration - 0.5, 0.1);
  console.error(`[openai] Sampling ${count} frames across ${formatDuration(duration)}`);
  for (let i = 0; i < count; i++) {
    const t = duration > 0 ? (usable * (i + 0.5)) / count : i;
    const outPath = join(workDir, `frame-${String(i).padStart(3, "0")}.jpg`);
    try {
      await execFileP("ffmpeg", [
        "-y",
        "-ss", t.toFixed(2),
        "-i", input.path,
        "-frames:v", "1",
        "-vf", "scale='min(1024,iw)':-2",
        "-q:v", "4",
        outPath,
      ]);
      if (existsSync(outPath)) frames.push({ timestamp: t, path: outPath });
    } catch (err) {
      console.error(`  [frame @${t.toFixed(1)}s] extraction failed: ${err.message}`);
    }
  }
  if (frames.length === 0) throw new Error("Failed to extract any frames from the video.");
  return frames;
}

async function extractTranscript(input, ffmeta, workDir) {
  if (!ffmeta?.audioCodec) {
    console.error("[openai] No audio stream detected — skipping transcription");
    return null;
  }
  const audioPath = join(workDir, "audio-track.mp3");
  try {
    await execFileP("ffmpeg", ["-y", "-i", input.path, "-vn", "-b:a", "64k", audioPath]);
    console.error("[openai] Transcribing audio track");
    return await openaiTranscribe(audioPath);
  } catch (err) {
    console.error(`[openai] Transcription skipped: ${err.message}`);
    return null;
  }
}

async function analyzeWithOpenAI(model, input, ffmeta, prompt, maxFrames, workDir) {
  const duration = ffmeta?.duration || 0;
  const frames = await extractFrames(input, duration, maxFrames, workDir);
  const transcript = await extractTranscript(input, ffmeta, workDir);

  const parts = [];
  parts.push({
    type: "text",
    text: `You are analyzing a video via ${frames.length} sampled frames${transcript ? " plus an audio transcript" : " (no audio transcript available)"}. Video duration: ${formatDuration(duration)}. Each frame is labeled with its timestamp. Treat gaps between frames as unobserved — do not invent events between samples.`,
  });
  for (const frame of frames) {
    parts.push({ type: "text", text: `Frame at ${formatDuration(frame.timestamp)}:` });
    const data = (await readFile(frame.path)).toString("base64");
    parts.push({ type: "image_url", image_url: { url: `data:image/jpeg;base64,${data}` } });
  }
  if (transcript) {
    parts.push({ type: "text", text: `Audio transcript:\n${transcript}` });
  }
  parts.push({ type: "text", text: prompt });

  console.error(`[openai] Video analysis starting using ${model}`);
  return openaiChat(model, parts);
}

// --- Output ---

function buildMarkdown({ ts, outDir, provider, model, mode, prompt, input, ffmeta, mimeType, analysis }) {
  const lines = [];
  lines.push(`# Video analysis - ${ts}\n`);
  lines.push(`Output: \`${outDir}\``);
  lines.push(`Provider: \`${provider}\` - Model: \`${model}\``);
  lines.push(`Mode: \`${mode}\``);
  if (prompt) lines.push(`Prompt: ${prompt}`);
  lines.push("");

  lines.push(`## ${input.title || basename(input.path)}`);
  if (input.sourceUrl) lines.push(`- Source: ${input.sourceUrl}`);
  lines.push(`- MIME type: ${mimeType}`);
  if (ffmeta && !ffmeta.error) {
    lines.push(`- Duration: ${formatDuration(ffmeta.duration)} - Size: ${formatSize(ffmeta.sizeBytes)}`);
    lines.push(`- Video: ${ffmeta.videoCodec || "?"} ${ffmeta.width || "?"}x${ffmeta.height || "?"} ${ffmeta.frameRate || ""}`.trim());
    if (ffmeta.audioCodec) lines.push(`- Audio: ${ffmeta.audioCodec}`);
  } else if (ffmeta?.error) {
    lines.push(`- ffprobe error: ${ffmeta.error}`);
  }
  lines.push("");

  lines.push("## Analysis\n");
  lines.push(analysis);
  lines.push("");

  return lines.join("\n");
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.file && !args.url) {
    console.error("ERROR: provide --file or --url");
    process.exit(2);
  }

  const { provider, note } = await resolveProvider(args.provider);
  if (note) console.error(`[provider] ${note}`);
  const model = args.model || DEFAULT_MODELS[provider];

  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const outDir = args.out ? resolve(args.out) : resolve(`video-analysis-output/${ts}`);
  const workDir = join(tmpdir(), `analyze-video-${Date.now()}`);
  await mkdir(outDir, { recursive: true });
  await mkdir(workDir, { recursive: true });

  let input = null;

  try {
    input = await prepareInput(args, workDir);
    const mimeType = mimeForFile(input.path);
    const ffmeta = await ffprobeFile(input.path);
    const prompt = buildPrompt(args);

    const analysis = provider === "gemini"
      ? await analyzeWithGemini(model, input, mimeType, prompt)
      : await analyzeWithOpenAI(model, input, ffmeta, prompt, args.maxFrames, workDir);

    const manifest = {
      timestamp: ts,
      outDir,
      provider,
      model,
      mode: args.mode,
      prompt: args.prompt,
      input: {
        path: input.path,
        title: input.title,
        sourceUrl: input.sourceUrl,
        mimeType,
        ffmeta,
      },
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
        input, ffmeta, mimeType, analysis,
      });
      await writeFile(join(outDir, "summary.md"), md);
      console.log(md);
    }
  } catch (err) {
    console.error("FATAL:", err.stack || err.message);
    process.exitCode = 1;
  } finally {
    if (input?.isTempFile && input.path && existsSync(input.path)) {
      await rm(input.path, { force: true }).catch(() => {});
    }
    await rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

main();
