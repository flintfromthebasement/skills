// Picks engines for a query; every rule is a cheap regex so agents can predict the route.
const SOCIAL = /\b(twitter|tweets?|x\.com|on x|people (are )?saying|sentiment|reaction|backlash|viral|trending|hype)\b|(^|\s)@\w+/i;
const LIVE = /\b(today|tonight|right now|breaking|this (morning|week)|just (announced|released|launched)|live)\b/i;
const COVERAGE = /\b(events?|list(s|ing)?|all the|every|roundup|options|alternatives|competitors|things to do|near(by)?|where (can|to)|compare|versus|vs\.?|landscape|who (sells|makes|offers)|find (me )?(all|some|places|people|shops))\b/i;
const QUICK = /^(what|who|when|where|which|how (many|much|old|long)|is|are|does|did|was)\b/i;

export const ALL = ['grok', 'perplexity', 'chatgpt'];

export function route(query) {
  if (SOCIAL.test(query)) return { engines: ['grok'], x: true, reason: 'social/X signal → grok with x_search' };
  if (COVERAGE.test(query)) return { engines: ALL, x: false, reason: 'coverage query (lists, events, comparisons) → all engines' };
  if (LIVE.test(query)) return { engines: ['grok', 'perplexity'], x: true, reason: 'live/breaking → grok (x) + perplexity' };
  if (QUICK.test(query) && query.split(/\s+/).length <= 14) return { engines: ['perplexity'], x: false, reason: 'short factual question → perplexity' };
  return { engines: ALL, x: false, reason: 'default → all engines' };
}
