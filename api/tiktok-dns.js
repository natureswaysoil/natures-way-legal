// TikTok DNS TXT Record Verification Endpoint
export default function handler(req, res) {
  // Set headers for DNS-like response
  res.setHeader('Content-Type', 'text/plain');
  res.setHeader('Cache-Control', 'public, max-age=300');
  
  // TikTok verification string
  const verification = 'tiktok-developers-site-verification=Vppdkkg17zPwMXE5vCnTmcHXvGI2moBj';
  
  // Handle different query types
  const { query } = req;
  const domain = req.headers.host;
  
  if (query.type === 'TXT' || query.record === 'TXT') {
    // Return TXT record format
    res.status(200).send(verification);
  } else if (query.format === 'json') {
    // Return JSON format for debugging
    res.setHeader('Content-Type', 'application/json');
    res.status(200).json({
      domain: domain,
      record_type: 'TXT',
      value: verification,
      ttl: 300,
      status: 'active',
      verified_for: ['tiktok-developers'],
      timestamp: new Date().toISOString()
    });
  } else {
    // Default: return verification string
    res.status(200).send(verification);
  }
}