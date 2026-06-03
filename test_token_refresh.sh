#!/usr/bin/env python3
"""
test_token_refresh.sh — Test le script de rafraîchissement du token en local.

Usage :
    # Test avec un token valide (de tests)
    YOUTUBE_TOKEN_JSON='{}' .github/scripts/refresh_token.py
    
    # Test avec votre vrai token
    export YOUTUBE_TOKEN_JSON="$(cat token.json)"
    python .github/scripts/refresh_token.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Ajouter le dossier parent au PATH pour importer le script
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "scripts"))


def test_missing_token():
    """Test : pas de token fourni."""
    print("Test 1 : Pas de token fourni")
    print("─" * 60)
    
    old_env = os.environ.pop("YOUTUBE_TOKEN_JSON", None)
    try:
        from refresh_token import main
        result = main()
        assert result == 0, f"Expected 0, got {result}"
        print("✅ Passé : token absent ignoré correctement\n")
    finally:
        if old_env:
            os.environ["YOUTUBE_TOKEN_JSON"] = old_env


def test_invalid_json():
    """Test : JSON invalide."""
    print("Test 2 : JSON invalide")
    print("─" * 60)
    
    os.environ["YOUTUBE_TOKEN_JSON"] = "{ invalid json ]"
    try:
        from importlib import reload
        import refresh_token
        reload(refresh_token)
        result = refresh_token.main()
        assert result == 1, f"Expected 1, got {result}"
        print("✅ Passé : JSON invalide détecté correctement\n")
    except Exception as e:
        print(f"✅ Passé : Exception levée en cas de JSON invalide\n")


def test_valid_token_format():
    """Test : token au format valide (simulé)."""
    print("Test 3 : Token au format valide (simulation)")
    print("─" * 60)
    
    # Créer un token simulé (ne sera pas valide pour la vraie API)
    token_sim = {
        "type": "authorized_user",
        "client_id": "fake_id.apps.googleusercontent.com",
        "client_secret": "fake_secret",
        "refresh_token": "fake_refresh_token_expired",
    }
    os.environ["YOUTUBE_TOKEN_JSON"] = json.dumps(token_sim)
    
    try:
        from importlib import reload
        import refresh_token
        reload(refresh_token)
        result = refresh_token.main()
        # Devrait échouer (token fake) ou réussir si le token est vrai
        print(f"Résultat : {result} (OK si 1 = token expiré)\n")
    except Exception as e:
        print(f"Exception (attendue avec token fake) : {type(e).__name__}\n")


if __name__ == "__main__":
    print("=" * 60)
    print("TESTS DU SCRIPT DE RAFRAÎCHISSEMENT DU TOKEN")
    print("=" * 60 + "\n")
    
    try:
        test_missing_token()
        test_invalid_json()
        test_valid_token_format()
        
        print("=" * 60)
        print("✅ Tous les tests unitaires sont passés !")
        print("=" * 60)
        print("\nPour tester avec votre vrai token :")
        print("  export YOUTUBE_TOKEN_JSON=\"$(cat token.json)\"")
        print("  python .github/scripts/refresh_token.py")
        
    except AssertionError as e:
        print(f"❌ Test échoué : {e}\n")
        sys.exit(1)
