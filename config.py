import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'levelup-it-resumes-secret-key-change-me')
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'resumes.db')
    DATA_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'resume_database.csv')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    
    @classmethod
    def is_postgres(cls):
        return bool(cls.DATABASE_URL)
    
    CREDIT_PACKS = {
        'starter': {'name': 'Starter Pack', 'credits': 50, 'price_cents': 2900, 'price_display': '$29'},
        'pro': {'name': 'Pro Pack', 'credits': 200, 'price_cents': 9900, 'price_display': '$99'},
        'growth': {'name': 'Growth Pack', 'credits': 500, 'price_cents': 19900, 'price_display': '$199'},
        'enterprise': {'name': 'Enterprise Pack', 'credits': 1000, 'price_cents': 34900, 'price_display': '$349'},
    }
    COST_PER_RESUME = 1
