# JARVIS Cloud V18

Backend FastAPI + Supabase para GPS, dispositivos e Modo Sentinela.

## Local
1. Rode `supabase.sql` no SQL Editor do Supabase.
2. Copie `.env.example` para `.env` e preencha as 3 variaveis obrigatorias.
3. `pip install -r requirements.txt`
4. Execute `start_cloud.bat` ou `python -m uvicorn app:app --host 0.0.0.0 --port 8100`.
5. Abra `http://127.0.0.1:8100/health`.

## Vercel
Use a pasta `cloud` como Root Directory do projeto Vercel. Cadastre `JARVIS_CLOUD_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` e opcionalmente `JARVIS_CORS_ORIGINS` em Environment Variables. O `.env` real nao deve ser enviado ao Git.
