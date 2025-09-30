// Vercel API endpoint to handle DNS TXT record verification for TikTok
export default function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  // Return TikTok verification for DNS TXT record queries
  const verification = 'tiktok-developers-site-verification=Vppdkkg17zPwMXE5vCnTmcHXvGI2moBj';
  
  res.status(200).json({
    verification: verification,
    domain: req.headers.host,
    method: 'DNS TXT Record',
    status: 'active',
    timestamp: new Date().toISOString()
  });
}