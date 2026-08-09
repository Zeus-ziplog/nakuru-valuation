export default function handler(req, res) {
  // Only allow GET requests
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Get token from environment variable
  const token = process.env.GITHUB_TOKEN;
  
  if (!token) {
    return res.status(404).json({ error: 'Token not configured' });
  }

  // Return the token
  return res.status(200).json({ token: token });
}
