# Models & fallbacks

The generator needs a **vision** model. Three tiers, preferred → last-resort.

## 1. OpenRouter — `google/gemini-3.1-flash-lite` (default, recommended)
What this skill was built and tuned on. Fast, accurate on photos/screenshots/logos, and cheap
(~$0.0004/image; a few thousand images is a couple of dollars).

```bash
export AI_API_KEY=sk-or-...          # or OPENROUTER_API_KEY
python3 generate.py --manifest manifest.json --tiers P1_content
```
Defaults: `AI_API_URL=https://openrouter.ai/api/v1/chat/completions`,
`AI_MODEL=google/gemini-3.1-flash-lite`. Cost comes back per-call in `usage.cost`.

## 2. Any OpenAI-compatible vision endpoint
`generate.py` speaks the standard `chat/completions` shape with
`image_url: {url: "data:image/jpeg;base64,..."}`. Point it anywhere:
```bash
# OpenAI directly
AI_API_URL=https://api.openai.com/v1/chat/completions AI_API_KEY=sk-... \
python3 generate.py --model gpt-4o-mini --manifest manifest.json
# Anthropic via an OpenAI-compatible gateway, a local vLLM/Ollama bridge, etc.
python3 generate.py --api-url http://localhost:11434/v1/chat/completions --model llava ...
```
Pick any capable, cheap vision model. Flash-Lite-class models are the sweet spot — alt text does
not need a frontier model.

## 3. No API key at all → Claude-Code-native fallback (zero external API)
If the only thing available is the host agent (Claude Code / another skills-capable agent) with
no vision API budget, use the agent's **own** vision instead of `generate.py`:

1. Fetch + downscale the images locally:
   ```bash
   python3 scripts/fetch_images.py --manifest manifest.json --tiers P1_content --limit 50
   # -> alt-images/<id>.jpg + alt-images/index.jsonl
   ```
2. The agent reads each `alt-images/<id>.jpg` with its file-read/vision tool, applies the prompt
   contract in `prompt-and-seo.md`, and appends one row per image to `results.jsonl` in exactly
   the shape `generate.py` produces:
   ```json
   {"id":123,"tier":"P1_content","url":"https://.../x.jpg","file":"2024/01/x.jpg","title":"",
    "pages":"","proposed_alt":"...","keyword_used":"","chars":NN,"needs_visual_review":false,
    "fetch_error":"","model_error":""}
   ```
   Read `index.jsonl` for each image's context (title/pages/url). Skip rows with a `fetch_error`
   (emit empty + `needs_visual_review:true`).
3. For volume, fan out: have the orchestrator dispatch sub-agents, each handling a batch of
   images, all appending to the same `results.jsonl`.
4. Continue normally: `make_gallery.py` → review → `apply_alt.php`.

This path is slower and uses the agent's context, so it's best for small/medium sites or a
zero-budget run. For thousands of images, tier 1 or 2 is far cheaper and faster.

## Notes
- Whatever model you use, the **prompt contract and post-processing live in the skill, not the
  model** (`prompt-and-seo.md`): accuracy-first, length cap, bolt-on stripper, no-guess-on-
  fetch-failure. Swapping models doesn't change the quality rules.
- Always validate on a 10-image sample and eyeball `gallery.html` before a full run, regardless
  of tier.
