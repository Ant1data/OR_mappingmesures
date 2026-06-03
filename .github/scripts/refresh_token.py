#!/usr/bin/env python3
"""
refresh_token.py — Rafraîchit régulièrement le token YouTube OAuth2.

À exécuter quotidiennement via GitHub Actions pour empêcher l'expiration du token.

Variables d'environnement :
    YOUTUBE_TOKEN_JSON : token OAuth2 YouTube sérialisé en JSON (fourni par GitHub Secrets)

Exit codes :
    0 : Token valide ou rafraîchi avec succès
    1 : Token expiré/invalide — regénération manuelle requise
"""

import json
import os
import sys
from pathlib import Path

try:
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("❌ Erreur : installer google-auth-oauthlib")
    print("   pip install google-auth-oauthlib")
    sys.exit(1)


def main() -> int:
    """Vérifier et rafraîchir le token YouTube."""
    
    # ── 1. Récupérer le token depuis les secrets GitHub ───────────────────────
    raw = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
    if not raw:
        print("⚠️  Aucun token fourni (YOUTUBE_TOKEN_JSON vide).")
        print("    → Ignorer (secret non configuré pour ce workflow)")
        return 0

    # ── 2. Parser le JSON ──────────────────────────────────────────────────────
    try:
        token_info = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ YOUTUBE_TOKEN_JSON : JSON invalide.")
        print(f"   Détail : {e}")
        return 1

    # ── 3. Créer les credentials ───────────────────────────────────────────────
    try:
        creds = Credentials.from_authorized_user_info(
            token_info,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
    except Exception as e:
        print(f"❌ Impossible de créer les credentials : {e}")
        return 1

    # ── 4. Vérifier et rafraîchir ──────────────────────────────────────────────
    try:
        if creds.expired and creds.refresh_token:
            print("🔄 Token expiré — Rafraîchissement en cours…")
            creds.refresh(Request())
            print("✅ Token rafraîchi avec succès.")
        elif creds.valid:
            print("✅ Token valide (pas de rafraîchissement nécessaire).")
        else:
            print("⚠️  Token non valide mais pas de refresh_token disponible.")
            print("   → Regénération manuelle requise (voir ci-dessous)")
            return 1

    except RefreshError as e:
        print(f"❌ Impossible de rafraîchir le token.")
        print(f"   Erreur : {e}")
        print()
        print("🚨 TOKEN EXPIRÉ OU RÉVOQUÉ")
        print("   (erreur : invalid_grant)")
        print()
        print("💡 Solution :")
        print("   1. Exécutez localement : python generate_token.py")
        print("   2. Copiez le contenu de token.json")
        print("   3. Allez dans Settings → Secrets and variables → Actions")
        print("   4. Mettez à jour le secret YOUTUBE_TOKEN_JSON")
        print("   5. Relancez ce workflow")
        return 1

    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
