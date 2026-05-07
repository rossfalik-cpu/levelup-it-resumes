# Level Up IT Resumes

Pay-per-resume IT recruiter database. Search, browse, and unlock contact details.

## Quick Deploy to Render

1. Push this repo to GitHub
2. Go to https://render.com → Dashboard → New + → Blueprint
3. Connect your GitHub repo
4. Render auto-detects render.yaml and deploys:
   - Web service (Flask app)
   - PostgreSQL database
5. Add your Stripe keys as environment variables:
   - STRIPE_PUBLIC_KEY
   - STRIPE_SECRET_KEY
6. Access at https://levelup-it-resumes.onrender.com
7. Login: admin / admin123

## Local Development

```bash
pip install -r requirements.txt
python seed.py
python app.py
# Open http://127.0.0.1:5050
```

## Tech Stack
- Flask (Python)
- PostgreSQL (production) / SQLite (local)
- Stripe for payments
- Gunicorn for production serving
