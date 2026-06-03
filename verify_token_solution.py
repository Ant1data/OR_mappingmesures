#!/usr/bin/env python3
"""
verify_token_solution.py — Vérifie que la solution est correctement en place.

Usage :
    python verify_token_solution.py
    
Exit codes :
    0 : Tout est OK
    1 : Des fichiers/configurations manquent
"""

import json
import sys
from pathlib import Path


def check_file_exists(path: Path, description: str) -> bool:
    """Vérifier qu'un fichier existe."""
    if path.exists():
        print(f"✅ {description}")
        print(f"   {path}")
        return True
    else:
        print(f"❌ {description} — MANQUANT")
        print(f"   Supposé être : {path}")
        return False


def check_file_content(path: Path, contains: str, description: str) -> bool:
    """Vérifier qu'un fichier contient un texte."""
    if not path.exists():
        print(f"❌ {description} — FICHIER MANQUANT")
        return False
    
    content = path.read_text(encoding='utf-8')
    if contains in content:
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} — CONTENU MANQUANT")
        print(f"   Recherché : '{contains[:50]}...'")
        return False


def main() -> int:
    """Vérifier la solution."""
    root = Path(__file__).parent
    all_ok = True
    
    print("=" * 70)
    print("🔍 VÉRIFICATION DE LA SOLUTION TOKEN YOUTUBE")
    print("=" * 70 + "\n")
    
    # ── Documentation ─────────────────────────────────────────────────────────
    print("📚 Documentation")
    print("─" * 70)
    
    all_ok &= check_file_exists(
        root / "LIRE_MOI_DABORD.md",
        "Guide d'introduction"
    )
    all_ok &= check_file_exists(
        root / "GUIDE_RAPIDE_TOKEN.md",
        "Guide rapide (5 min)"
    )
    all_ok &= check_file_exists(
        root / "CHECKLIST_MISE_EN_PLACE.md",
        "Checklist de mise en place"
    )
    all_ok &= check_file_exists(
        root / "PROBLEME_TOKEN_EXPLICATION.md",
        "Documentation complète du problème"
    )
    all_ok &= check_file_exists(
        root / "SYNTHESE_CORRECTIONS.md",
        "Résumé technique des corrections"
    )
    all_ok &= check_file_exists(
        root / "ARCHITECTURE_SOLUTION.md",
        "Diagramme d'architecture"
    )
    
    print()
    
    # ── Automation (workflows) ────────────────────────────────────────────────
    print("⚙️  Automation")
    print("─" * 70)
    
    workflow_path = root / ".github" / "workflows" / "refresh-token.yml"
    all_ok &= check_file_exists(
        workflow_path,
        "Workflow quotidien de rafraîchissement du token"
    )
    
    script_path = root / ".github" / "scripts" / "refresh_token.py"
    all_ok &= check_file_exists(
        script_path,
        "Script Python de vérification/rafraîchissement"
    )
    
    print()
    
    # ── Amélioration du code ──────────────────────────────────────────────────
    print("💻 Améliorations du code")
    print("─" * 70)
    
    all_ok &= check_file_content(
        root / "upload_youtube.py",
        "🚨 JETON YOUTUBE EXPIRÉ",
        "Messages d'erreur améliorés dans upload_youtube.py"
    )
    
    print()
    
    # ── Tests ─────────────────────────────────────────────────────────────────
    print("🧪 Tests")
    print("─" * 70)
    
    all_ok &= check_file_exists(
        root / "test_token_refresh.sh",
        "Tests unitaires du script de rafraîchissement"
    )
    
    print()
    
    # ── Configuration README ──────────────────────────────────────────────────
    print("📖 Configuration README")
    print("─" * 70)
    
    all_ok &= check_file_content(
        root / "README.md",
        "Troubleshooting",
        "Section Troubleshooting dans README.md"
    )
    
    print()
    
    # ── Résumé ────────────────────────────────────────────────────────────────
    print("=" * 70)
    if all_ok:
        print("✅ TOUT EST OK !")
        print()
        print("Prochaines étapes :")
        print("  1. Lisez LIRE_MOI_DABORD.md")
        print("  2. Suivez CHECKLIST_MISE_EN_PLACE.md")
        print("  3. Puis commitez et poushez les fichiers")
        print()
        return 0
    else:
        print("❌ IL MANQUE DES FICHIERS")
        print()
        print("Vérifiez que tous les fichiers listés ci-dessus existent.")
        print("Si un fichier manque, consultez la documentation pour le créer.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
