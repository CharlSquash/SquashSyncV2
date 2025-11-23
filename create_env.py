content = "SECRET_KEY=django-insecure-local-dev-key-12345\nDEV_MODE=True\n"
with open('.env', 'w', encoding='utf-8') as f:
    f.write(content)
print("Created .env with clean UTF-8")
