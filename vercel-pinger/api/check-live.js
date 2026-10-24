export default async function handler(req, res) {
  const targetBase = process.env.RENDER_URL;
  const token = process.env.CRON_TOKEN || process.env.SQLADMIN_RAW_PASSWORD || "";

  if (!targetBase) {
    return res.status(400).json({
      status: "error",
      message: "Please set RENDER_URL in Vercel Environment Variables (e.g. https://shopcl.onrender.com)"
    });
  }

  const cleanBase = targetBase.replace(/\/health\/?$/, "").replace(/\/+$/, "");
  const targetUrl = `${cleanBase}/api/cron/check-live?token=${encodeURIComponent(token)}&delete_die=true`;

  try {
    const startTime = Date.now();
    const response = await fetch(targetUrl);
    const data = await response.json();
    const durationMs = Date.now() - startTime;

    return res.status(response.status).json({
      status: "success",
      target: targetUrl,
      http_status: response.status,
      duration_ms: durationMs,
      result: data
    });
  } catch (error) {
    return res.status(500).json({
      status: "error",
      target: targetUrl,
      error: error.message
    });
  }
}
