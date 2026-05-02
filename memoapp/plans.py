PLAN_CONFIG = {
    "free": {
        "key": "free",
        "name": "Ücretsiz",
        "price": "₺0",
        "limit": 2,
        "brand_enabled": False,
        "description": "2 analiz hakkı, sadece video memorability.",
    },
    "starter": {
        "key": "starter",
        "name": "Başlangıç",
        "price": "$99 / ay",
        "limit": 3,
        "brand_enabled": False,
        "description": "Günlük 3 analiz, sadece video memorability.",
    },
    "pro": {
        "key": "pro",
        "name": "Profesyonel",
        "price": "$219 / ay",
        "limit": 25,
        "brand_enabled": True,
        "description": "Günlük 25 analiz, video + marka memorability.",
    },
    "enterprise": {
        "key": "enterprise",
        "name": "Kurumsal",
        "price": "Pay as you go",
        "limit": None,
        "brand_enabled": True,
        "description": "Sınırsız analiz, video + marka memorability.",
    },
}

def get_plan_config(plan_key):
    return PLAN_CONFIG.get(plan_key, PLAN_CONFIG["pro"])
