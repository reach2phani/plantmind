// The judge connector: promptfoo's grading calls go to Groq through this file.
//
// WHY THIS EXISTS (found 2026-10-28, smoke test)
//   Grading one answer took 19 minutes. The Qwen judge allows 7,000 input
//   tokens a minute; when a call hits that, Groq answers 429 "try again in
//   0.95s". promptfoo's built-in Groq connector instead waits for the reset of
//   a DIFFERENT counter (x-ratelimit-reset-requests, a daily request counter),
//   about 6 minutes, every time (promptfoo computeRateLimitWaitMs). This file
//   does the same call but waits only as long as Groq says — the same rule
//   PlantMind uses itself (multi_agent._retry_after_seconds).
//
// WHAT IT DOES NOT CHANGE
//   Same model, same settings (temperature 0, hidden reasoning), same grading
//   prompt promptfoo builds. Only the waiting is different.
//
// USED BY eval_fl101.yaml:
//   defaultTest.options.provider: { id: 'file://lib/groq_judge.js', config: {...} }

const URL = 'https://api.groq.com/openai/v1/chat/completions';
const MAX_RETRIES = 8;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Groq writes the wait three ways: "951.43ms", "1.07s", "1m2.5s".
// -> milliseconds (+0.5 s cushion), at most 60 s (the limits reset each minute)
function retryAfterMs(text, headers) {
  const t = text || '';
  const ms = /try again in\s+([\d.]+)ms/i.exec(t);
  if (ms) return Math.min(60000, Number(ms[1]) + 500);
  const m = /try again in\s+(?:(\d+)m\s*)?([\d.]+)s/i.exec(t);
  if (m) return Math.min(60000, ((Number(m[1] || 0) * 60) + Number(m[2])) * 1000 + 500);
  const ra = headers && headers.get && headers.get('retry-after');
  if (ra && !Number.isNaN(Number(ra))) return Math.min(60000, Number(ra) * 1000 + 500);
  return 5000;
}

// promptfoo hands the grading prompt over as text; for llm-rubric it is a
// JSON list of chat messages. Anything else is sent as one user message.
function toMessages(prompt) {
  try {
    const parsed = JSON.parse(prompt);
    if (Array.isArray(parsed) && parsed.every((m) => m && m.role && 'content' in m)) return parsed;
  } catch (e) { /* plain text */ }
  return [{ role: 'user', content: String(prompt) }];
}

class GroqJudge {
  constructor(options = {}) {
    this.config = options.config || {};
    this.model = this.config.model || 'qwen/qwen3.8-27b';
    this.label = options.label || `plantmind-judge:${this.model}`;
    this.fetch = this.config._fetch || fetch;   // _fetch: for the offline self-test only
    this.sleep = this.config._sleep || sleep;
  }

  id() {
    return this.label;
  }

  async callApi(prompt) {
    const key = process.env.GROQ_API_KEY;
    if (!key) return { error: 'GROQ_API_KEY is not set (run promptfoo with --env-file .env)' };
    const body = {
      model: this.model,
      messages: toMessages(prompt),
      temperature: this.config.temperature ?? 0,
      max_completion_tokens: this.config.max_completion_tokens ?? 2048,
    };
    if (this.config.reasoning_format) body.reasoning_format = this.config.reasoning_format;

    let waitedMs = 0;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      let res;
      try {
        res = await this.fetch(URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
          body: JSON.stringify(body),
        });
      } catch (e) {
        if (attempt === MAX_RETRIES) return { error: `judge network error: ${e.message}` };
        await this.sleep(5000);
        waitedMs += 5000;
        continue;
      }
      const text = await res.text();
      if (res.status === 429 || res.status >= 500) {
        if (attempt === MAX_RETRIES) return { error: `judge gave up after ${attempt + 1} tries: ${text.slice(0, 200)}` };
        const ms = res.status === 429 ? retryAfterMs(text, res.headers) : 5000;
        await this.sleep(ms);
        waitedMs += ms;
        continue;
      }
      if (!res.ok) return { error: `judge HTTP ${res.status}: ${text.slice(0, 300)}` };
      const data = JSON.parse(text);
      const usage = data.usage || {};
      return {
        output: (data.choices && data.choices[0] && data.choices[0].message.content) || '',
        tokenUsage: {
          total: usage.total_tokens || 0,
          prompt: usage.prompt_tokens || 0,
          completion: usage.completion_tokens || 0,
          numRequests: attempt + 1,
        },
        metadata: { judgeWaitedMs: waitedMs, judgeAttempts: attempt + 1 },
      };
    }
    return { error: 'judge: unreachable' };
  }
}

module.exports = GroqJudge;
module.exports.retryAfterMs = retryAfterMs;
module.exports.toMessages = toMessages;
