"""Read-only access to the public market-data endpoints that Kalshi and Polymarket document officially.

This package does not reverse engineer, scrape, or log in to anything. It calls only the three documented
public hosts in http.ALLOWED_HOSTS, sends no credentials, and throttles requests. Check each platform's terms
and your own eligibility before using it. Fetched data is for your own research and is not committed to the repo.
"""
