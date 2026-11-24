export default async function handler(req, res) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    res.status(500).json({ detail: 'BACKEND_URL is not configured' });
    return;
  }

  try {
    const rawPath = req.query.path;
    const segments = Array.isArray(rawPath) ? rawPath : rawPath ? [rawPath] : [];
    const query = new URLSearchParams();

    for (const [key, value] of Object.entries(req.query)) {
      if (key === 'path' || value === undefined) continue;
      if (Array.isArray(value)) {
        for (const item of value) query.append(key, String(item));
      } else {
        query.append(key, String(value));
      }
    }

    const suffix = segments.map((segment) => encodeURIComponent(String(segment))).join('/');
    const queryString = query.toString();
    const target = `${backendUrl.replace(/\/$/, '')}/api/${suffix}${queryString ? `?${queryString}` : ''}`;

    const headers = {};
    if (req.headers.authorization) headers.authorization = req.headers.authorization;
    if (req.headers['content-type']) headers['content-type'] = req.headers['content-type'];
    if (req.headers.accept) headers.accept = req.headers.accept;

    const method = req.method || 'GET';
    const hasBody = method !== 'GET' && method !== 'HEAD';
    let body;
    if (hasBody) {
      if (Buffer.isBuffer(req.body)) body = req.body;
      else if (typeof req.body === 'string') body = req.body;
      else body = JSON.stringify(req.body ?? {});
    }

    const upstream = await fetch(target, { method, headers, body });
    const text = await upstream.text();
    const contentType = upstream.headers.get('content-type');

    res.status(upstream.status);
    if (contentType) res.setHeader('content-type', contentType);
    res.send(text);
  } catch (error) {
    res.status(502).json({ detail: error instanceof Error ? error.message : 'Backend request failed' });
  }
}
