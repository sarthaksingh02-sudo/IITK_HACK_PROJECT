.PHONY: keys demo test install clean

install:
	pip install -r requirements.txt

keys:
	@echo "Generating Ed25519 keypair..."
	@if not exist keys mkdir keys
	python -c "\
import nacl.signing, pathlib;\
sk = nacl.signing.SigningKey.generate();\
pathlib.Path('keys/private.key').write_bytes(bytes(sk));\
pathlib.Path('keys/public.key').write_bytes(bytes(sk.verify_key));\
print('Keys written to keys/private.key and keys/public.key');\
print('NOTE: Never commit private.key to version control.');\
"

test:
	pytest -v shared/tests/ tests/

demo:
	@echo "=== AccessAI Demo Launcher ==="
	powershell -ExecutionPolicy Bypass -File run_demo.ps1

clean:
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	@if exist cloud\cloud.db del cloud\cloud.db
	@if exist hub\hub.db del hub\hub.db
	@echo Cleaned.
