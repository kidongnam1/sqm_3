// SQM v8.6.6
// FastAPI 호출 표준 래퍼. 재시도 3회, 지수백오프.
const API_BASE = 'http://127.0.0.1:8765';
const DEFAULT_TIMEOUT_MS = 5000;

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function withTimeout(promise, ms) {
  return await Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new ApiError('timeout', 0)), ms)
    ),
  ]);
}

export async function apiCall(method, path, body = null, { timeout = DEFAULT_TIMEOUT_MS, retries = 3 } = {}) {
  const url = path.startsWith('http') ? path : API_BASE + path;
  const opts = {
    method: method.toUpperCase(),
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== null && ['POST', 'PUT', 'DELETE'].includes(opts.method)) {
    opts.body = JSON.stringify(body);
  }
  let lastErr = null;
  for (let i = 0; i < retries; i++) {
    try {
      const res = await withTimeout(fetch(url, opts), timeout);
      if (!res.ok) {
        let detail = null;
        try { detail = await res.json(); } catch {}
        throw new ApiError(`HTTP ${res.status}`, res.status, detail);
      }
      try { return await res.json(); }
      catch { return {}; }
    } catch (e) {
      lastErr = e;
      // 501 "준비 중" 은 재시도 무의미
      if (e.status === 501 || e.status === 404) throw e;
      // 지수백오프 500ms / 1s / 2s
      if (i < retries - 1) await new Promise(r => setTimeout(r, 500 * (2 ** i)));
    }
  }
  throw lastErr || new ApiError('unknown', 0);
}

export const apiGet = (path, opts) => apiCall('GET', path, null, opts);
export const apiPost = (path, body, opts) => apiCall('POST', path, body, opts);
export const apiPut = (path, body, opts) => apiCall('PUT', path, body, opts);
export const apiDelete = (path, opts) => apiCall('DELETE', path, null, opts);

// 전역 노출 (기존 app.js 호환)
if (typeof window !== 'undefined') {
  window.api = { get: apiGet, post: apiPost, put: apiPut, delete: apiDelete };
}
