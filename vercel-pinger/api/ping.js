export default async function handler(req, res) {
  const targetUrl = process.env.RENDER_URL;

  if (!targetUrl) {
    return res.status(400).json({
      status: "error",
      message: "Please set RENDER_URL in Vercel Environment Variables (e.g. https://your-bot.onrender.com/health)"
    });
  }

  try {
    const startTime = Date.now();
    const response = await fetch(targetUrl);
    const data = await response.text();
    const durationMs = Date.now() - startTime;

    return res.status(200).json({
      status: "success",
      target: targetUrl,
      http_status: response.status,
      duration_ms: durationMs,
      response: data
    });
  } catch (error) {
    return res.status(500).json({
      status: "error",
      target: targetUrl,
      error: error.message
    });
  }
}
