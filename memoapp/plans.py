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

PLAN_ALIASES = {
    "ucretsiz": "free",
    "ücretsiz": "free",
    "baslangic": "starter",
    "başlangıç": "starter",
    "starter": "starter",
    "pro": "pro",
    "profesyonel": "pro",
    "enterprise": "enterprise",
    "kurumsal": "enterprise",
}


def normalize_plan_key(plan_key):
    if not plan_key:
        return "free"
    lowered = str(plan_key).strip().lower()
    return PLAN_ALIASES.get(lowered, lowered if lowered in PLAN_CONFIG else "free")


def get_plan_config(plan_key):
    normalized = normalize_plan_key(plan_key)
    return PLAN_CONFIG[normalized]
