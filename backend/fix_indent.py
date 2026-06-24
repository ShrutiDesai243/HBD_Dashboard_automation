with open('config.py', 'r', errors='ignore') as f:
    content = f.read()

# 3 spaces wali line fix karo
content = content.replace(
    '   SQLALCHEMY_DATABASE_URI = (',
    '    SQLALCHEMY_DATABASE_URI = ('
)

with open('config.py', 'w') as f:
    f.write(content)

print("Fixed!")