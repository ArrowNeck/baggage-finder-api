Chat feature patch for Baggage-Finder-API
=========================================
Copy these files into your project at the same paths.

NEW files (they don't exist in your project yet - just add them):
  app/models/chat.py
  alembic/versions/0003_chat.py        <- set down_revision to your latest revision id (alembic heads)
  app/repositories/chat_repository.py
  app/schemas/chat.py
  app/services/chat_service.py
  app/services/realtime_service.py
  app/api/v1/endpoints/conversations.py
  firestore.rules
  firebase.json

REPLACE files (you already have these; compare first, e.g. `diff -u yours patch`, then replace):
  app/api/v1/endpoints/public.py
  app/services/push_service.py
  app/services/baggage_service.py
  app/api/web.py
  app/web/qr.html                      <- keep the __NONCE__ and __API_PREFIX__ placeholders

Then make the small edits listed in the chat message
(models/__init__.py, core/enums.py, core/routes.py, core/config.py, .env.example,
 api/v1/api.py, api/v1/endpoints/users.py, services/public_service.py),
run `alembic upgrade head`, and redeploy.
