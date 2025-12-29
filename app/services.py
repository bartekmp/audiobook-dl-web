"""
Audiobook service definitions and configurations
"""

# Supported audiobook services
SUPPORTED_SERVICES = {
    "storytel": {
        "name": "Storytel / Mofibo",
        "auth_methods": ["login"],
        "login_fields": ["username", "password"],
        "requires_shelf": True,
        "example_url": "https://www.storytel.com/pl/books/example-book-12345",
    },
    "saxo": {
        "name": "Saxo",
        "auth_methods": ["login"],
        "login_fields": ["username", "password"],
        "requires_shelf": False,
        "example_url": "https://www.saxo.com/en/book-name",
    },
    "nextory": {
        "name": "Nextory",
        "auth_methods": ["login"],
        "login_fields": ["username", "password"],
        "requires_shelf": False,
        "example_url": "https://nextory.com/book/example",
    },
    "ereolen": {
        "name": "eReolen",
        "auth_methods": ["cookies", "login"],
        "login_fields": ["username", "password", "library"],
        "requires_shelf": False,
        "example_url": "https://ereolen.dk/ting/object/example",
    },
    "podimo": {
        "name": "Podimo",
        "auth_methods": ["login"],
        "login_fields": ["username", "password"],
        "requires_shelf": False,
        "example_url": "https://podimo.com/book/example",
    },
    "yourcloudlibrary": {
        "name": "YourCloudLibrary",
        "auth_methods": ["cookies", "login"],
        "login_fields": ["username", "password", "library"],
        "requires_shelf": False,
        "example_url": "https://www.yourcloudlibrary.com/title/example",
    },
    "everand": {
        "name": "Everand (Scribd)",
        "auth_methods": ["cookies"],
        "login_fields": [],
        "requires_shelf": False,
        "example_url": "https://everand.com/book/example",
    },
}
