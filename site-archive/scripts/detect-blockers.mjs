const BLOCKER_SIGNATURES = [
  {
    id: 'cloudflare-just-a-moment',
    reason: 'Cloudflare challenge page',
    patterns: [/just a moment/i, /checking your browser before accessing/i, /cf-browser-verification/i]
  },
  {
    id: 'human-verification',
    reason: 'Human verification page',
    patterns: [/are you human/i, /verify you are human/i, /prove you are human/i]
  },
  {
    id: 'captcha',
    reason: 'Captcha or challenge form',
    patterns: [/captcha/i, /hcaptcha/i, /recaptcha/i]
  },
  {
    id: 'javascript-cookies-required',
    reason: 'JavaScript or cookies required challenge',
    patterns: [/enable javascript and cookies/i, /requires javascript/i, /cookies are required/i]
  },
  {
    id: 'akamai-bot-manager',
    reason: 'Akamai bot manager challenge',
    patterns: [/akamai/i, /reference #[a-f0-9.]+/i, /access denied/i]
  },
  {
    id: 'datadome',
    reason: 'DataDome bot protection page',
    patterns: [/datadome/i, /captcha delivered by datadome/i]
  },
  {
    id: 'perimeterx',
    reason: 'PerimeterX bot protection page',
    patterns: [/perimeterx/i, /press and hold/i]
  }
];

function getTitle(html) {
  const match = html.match(/<title[^>]*>([^<]*)<\/title>/i);
  return match ? match[1].trim() : '';
}

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function fingerprintBlocker(blocker) {
  return `${blocker.id}:${blocker.reason}`.toLowerCase();
}

export function detectBlocker(html, statusCode, url) {
  if (!html || typeof html !== 'string') return null;

  const title = getTitle(html);
  const bodyText = stripHtml(html).slice(0, 4000);
  const haystack = `${title}\n${bodyText}`;

  for (const signature of BLOCKER_SIGNATURES) {
    if (signature.patterns.some((pattern) => pattern.test(haystack))) {
      return {
        id: signature.id,
        reason: signature.reason,
        title,
        statusCode,
        url
      };
    }
  }

  const lowContentChallenge =
    bodyText.length < 400 &&
    /(challenge|captcha|human|browser|verify|access denied|enable javascript)/i.test(haystack);

  if (lowContentChallenge) {
    return {
      id: 'generic-low-content-challenge',
      reason: 'Likely low-content challenge page',
      title,
      statusCode,
      url
    };
  }

  if ([403, 429, 503].includes(statusCode) && /(access denied|temporarily unavailable|blocked)/i.test(haystack)) {
    return {
      id: 'blocked-status-page',
      reason: 'Blocked status page',
      title,
      statusCode,
      url
    };
  }

  return null;
}
