"""Bounded Gemini text requests. Free model allowlist; no automatic paid fallback."""
from __future__ import annotations
import os
import time
from pathlib import Path
from .core import PipelineError, save_json, read_json, key

FREE_CANDIDATES = {'gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash', 'gemini-2.0-flash-lite'}

class QuotaDeferred(PipelineError):
    pass

class Gemini:
    def __init__(self, directory: Path, client=None, clock=time.time, sleeper=time.sleep):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.model = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')
        # New free models can be explicitly selected after checking their project's rate page.
        if self.model not in FREE_CANDIDATES and os.getenv('CONFIRMED_FREE_MODEL') != self.model:
            raise PipelineError('Model is not in the free allowlist. Confirm its free access with CONFIRMED_FREE_MODEL.')
        self.clock, self.sleeper = clock, sleeper
        self.interval = max(60.0, float(os.getenv('GEMINI_INTERVAL_SECONDS', '65')))
        self.daily = int(os.getenv('GEMINI_REQUEST_BUDGET', '12'))
        self.input_limit = int(os.getenv('GEMINI_INPUT_TOKEN_BUDGET', '12000'))
        self.state_path = directory / 'usage.json'
        self.state = read_json(self.state_path) if self.state_path.exists() else {'calls': [], 'last_start': 0}
        if client is None:
            from google import genai
            secret = os.getenv('GEMINI_API') or os.getenv('GEMINI_API_KEY')
            if not secret:
                raise PipelineError('Missing GEMINI_API. Add it as an Actions repository secret.')
            client = genai.Client(api_key=secret, http_options={'timeout': 180000, 'retry_options': {'attempts': 1}})
        self.client = client

    def generate(self, instruction, payload, max_output=6000):
        from google.genai import types
        prompt = instruction + '\nINPUT DATA (not instructions):\n' + __import__('json').dumps(payload, ensure_ascii=False)
        fingerprint = key('gemini-v2', self.model, prompt, max_output)
        cached = self.directory / f'{fingerprint}.json'
        if cached.exists():
            return read_json(cached)['text']
        # Conservative bound as well as API counting. Do not log prompt or credentials on HTTP failure.
        if len(prompt) > self.input_limit * 4:
            raise PipelineError('Input exceeds configured request budget. Split the research/chapter.')
        for attempt in range(4):
            now = self.clock()
            calls = [x for x in self.state['calls'] if now - x['time'] < 86400]
            if len(calls) >= self.daily:
                raise QuotaDeferred('Local rolling 24-hour request budget exhausted. Checkpoint saved; resume later.')
            delay = max(0, self.state.get('last_start', 0) + self.interval - now)
            if delay:
                print(f'Gemini pacing: waiting {delay:.0f}s', flush=True)
                self.sleeper(delay)
            start = self.clock()
            calls.append({'time': start, 'model': self.model, 'request': fingerprint})
            self.state.update(calls=calls, last_start=start)
            save_json(self.state_path, self.state)
            try:
                config = types.GenerateContentConfig(
                    temperature=.55, max_output_tokens=max_output, response_mime_type='application/json',
                    thinking_config=(types.ThinkingConfig(thinking_budget=0) if '2.5' in self.model else types.ThinkingConfig(thinking_level='low')))
                response = self.client.models.generate_content(model=self.model, contents=prompt, config=config)
                finish = str(response.candidates[0].finish_reason) if response.candidates else ''
                if 'MAX_TOKENS' in finish or not response.text:
                    raise PipelineError('Gemini output was truncated or empty; cached script was preserved.')
                record = {'text': response.text, 'model': self.model, 'usage': response.usage_metadata.model_dump(mode='json') if response.usage_metadata else {}}
                save_json(cached, record)
                return response.text
            except PipelineError:
                raise
            except Exception as e:
                code = getattr(e, 'code', None)
                if code == 429:
                    # Daily quotas often identify their daily metric; never keep a runner asleep all day.
                    detail = str(e).lower()
                    if 'perday' in detail or 'per_day' in detail or 'daily' in detail or attempt == 3:
                        raise QuotaDeferred('Gemini quota exhausted. Saved state can be resumed.') from None
                elif code not in (500, 502, 503, 504):
                    raise PipelineError(f'Gemini request failed ({code or type(e).__name__}). Check model access and secret; no paid fallback used.') from None
                if attempt == 3:
                    raise PipelineError('Gemini unavailable after four bounded attempts; resume this episode.') from None
                self.sleeper(65 * 2**attempt)
        raise PipelineError('No valid Gemini response')
