async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks);
}

module.exports = async function handler(req, res) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    res.statusCode = 500;
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ detail: 'BACKEND_URL is not configured' }));
    return;
  }

  try {
    const incoming = new URL(req.url || '/', 'http://localhost');
    const path = incoming.pathname.replace(/^\/api\/?/, '');
    const segments = path
      .split('/')
      .filter(Boolean)
      .map((segment) => encodeURIComponent(decodeURIComponent(segment)));
    const query = new URLSearchParams();
    for (const [key, value] of incoming.searchParams) query.append(key, value);
    if (!incoming.search && req.query) {
      for (const [key, value] of Object.entries(req.query)) {
        if (value === undefined) continue;
        if (Array.isArray(value)) {
          for (const item of value) query.append(key, String(item));
        } else {
          query.append(key, String(value));
        }
      }
    }
    const queryString = query.toString();
    const target = `${backendUrl.replace(/\/$/, '')}/api/${segments.join('/')}${queryString ? `?${queryString}` : ''}`;

    const headers = {};
    for (const name of ['authorization', 'content-type', 'accept']) {
      const value = req.headers[name];
      if (value) headers[name] = value;
    }

    const hasBody = !['GET', 'HEAD'].includes(req.method || 'GET');
    const body = hasBody ? await readBody(req) : undefined;
    const upstream = await fetch(target, { method: req.method || 'GET', headers, body });
    const text = await upstream.text();
    const contentType = upstream.headers.get('content-type');

    res.statusCode = upstream.status;
    if (contentType) res.setHeader('content-type', contentType);
    res.end(text);
  } catch (error) {
    res.statusCode = 502;
    res.setHeader('content-type', 'application/json');
    res.end(
      JSON.stringify({ detail: error instanceof Error ? error.message : 'Backend request failed' }),
    );
  }
};
