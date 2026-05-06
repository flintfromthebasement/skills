# Token estimation

You almost never have a real tokenizer at hand when filling this artifact. That's fine — approximate is useful, fabricated isn't.

## The default rule

```
tokens ≈ chars / 4
```

Works for English prose. Cite it in the footer.

## When to deviate

- **Code / JSON / structured data:** denser → `chars / 3.5` is closer.
- **Non-Latin scripts (CJK, Arabic, Cyrillic):** sparser → `chars / 1.5` or so. The Anthropic and OpenAI tokenizers spend more tokens per character there.
- **Long repeated tokens (e.g. URLs, base64 blobs):** unpredictable. Round generously.
- **Tool schemas:** roughly 400 tokens per schema once you include parameter docs.
- **The harness system prompt for Claude Code default install:** ~5,000 tokens.

## When to use a real tokenizer

If you're inside a Node or Python environment with the Anthropic SDK or `@anthropic-ai/tokenizer` available, use it. The skill doesn't ship a tokenizer because it would add an install step for a marginal accuracy gain.

```js
// JS, if you have @anthropic-ai/tokenizer or similar:
import { countTokens } from '@anthropic-ai/tokenizer';
const t = countTokens(content);
```

```python
# Python, if you have anthropic:
from anthropic import Anthropic
client = Anthropic()
n = client.messages.count_tokens(model="claude-opus-4-5", messages=[{"role": "user", "content": text}])
```

If you do this, drop the "approximate" caveat from the footer.

## Ground truth for current usage

For Claude Code specifically, the status bar at the bottom of the terminal shows the model's reported token count. That's a more reliable `tokensUsed` figure than your sum of per-block estimates — they'll usually disagree by 10–20% because of tokenizer overhead, cached schema repetition, and message metadata you can't see from inside the loop.

When both numbers are available:

- Use the model's reported figure as `tokensUsed`.
- Keep your per-block estimates for `tokens` so the breakdown grid still shows proportions.
- Note the discrepancy in the footer: "Model status bar reports 76k; sum of per-block estimates is 64k. Difference is mostly tokenizer overhead and cached tool-schema repetition."

## Don't get cute

It is not worth two paragraphs of footer to explain why your token math is exactly right. Approximate is fine. Honest is the bar.
