# utils/searcher.py

def common_patterns_db():
    return [
        {
            "trigger": "unity 3d game",
            "standard_features": [
                "Main Menu UI", "Controllable Character", "Basic Enemy AI", "Health System"
            ],
            "creative_addons": [
                "Day/Night Cycle", "Weather System", "Screenshot Mode", "Customizable Player"
            ]
        },
        {
            "trigger": "web app",
            "standard_features": ["Login", "Registration", "Dashboard"],
            "creative_addons": ["Dark Mode", "Live Chat", "Voice Navigation"]
        }
        # Expandable database
    ]
