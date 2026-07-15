# -*- coding: utf-8 -*-
"""
main.py
-------
Point d'entrée de la pipeline heurist_to_tei.

Étapes :
    1. Connexion à Heurist via LostmaDB et synchronisation
    2. Construction du DataFrame texts enrichi (build_texts)
    3. Construction du DataFrame witnesses enrichi (build_witnesses)
    4. Sérialisation des texts en fichiers TEI XML (serialize_texts)
    5. Sérialisation des witnesses en fichiers TEI XML (serialize_witnesses)
    6. Récupération et intégration des stemmata OpenStemmata (fetch_and_integrate_from_df)

Usage :
    python main.py
    python main.py --languages "dum (Middle Dutch)" "fro (Old French)"
    python main.py --languages "dum (Middle Dutch)" --output ./output/dum

Prérequis :
    - Fichier .env à la racine avec HEURIST_LOGIN et HEURIST_PASSWORD
    - pip install -r requirements.txt
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from lostma_db import LostmaDB

from src.tei import (
    build_texts,
    build_witnesses,
    serialize_texts,
    serialize_witnesses,
    fetch_and_integrate_from_df,
)


# ── Configuration du logging ──────────────────────────────────

def setup_logging(output_dir: Path) -> Path:
    log_file = output_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    return log_file


# ── Pipeline ──────────────────────────────────────────────────

def run(available_languages: list[str], output_dir: Path) -> None:

    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = setup_logging(output_dir)
    log = logging.getLogger(__name__)

    log.info("=" * 60)
    log.info("  Pipeline heurist_to_tei")
    log.info("=" * 60)
    log.info(f"  Langues        : {', '.join(available_languages)}")
    log.info(f"  Dossier sortie : {output_dir}")
    log.info("")

    # ── Étape 0 : connexion Heurist ───────────────────────────
    log.info("── Étape 0 : Connexion et synchronisation Heurist ──────")
    load_dotenv()
    login = os.getenv("HEURIST_LOGIN")
    pwd   = os.getenv("HEURIST_PASSWORD")

    if not login or not pwd:
        log.error("HEURIST_LOGIN ou HEURIST_PASSWORD absent du fichier .env")
        sys.exit(1)

    db = LostmaDB(login, pwd)
    db.sync()
    log.info("  ✓ Synchronisation terminée.")
    log.info("")

    # ── Étape 1 : build_texts ─────────────────────────────────
    log.info("── Étape 1 : Construction du DataFrame texts ────────────")
    texts_df = build_texts(db, available_languages)
    log.info(f"  {len(texts_df)} ligne(s) texts chargée(s).")
    log.info("")

    # ── Étape 2 : build_witnesses ─────────────────────────────
    log.info("── Étape 2 : Construction du DataFrame witnesses ────────")
    witnesses_df = build_witnesses(db, available_languages)
    log.info(f"  {len(witnesses_df)} ligne(s) witnesses chargée(s).")
    log.info("")

    # ── Étape 3 : serialize_texts ─────────────────────────────
    log.info("── Étape 3 : Sérialisation des texts ───────────────────")
    texts_output = output_dir / "texts"
    serialize_texts(texts_df, texts_output)
    log.info("")

    # ── Étape 4 : serialize_witnesses ─────────────────────────
    log.info("── Étape 4 : Sérialisation des witnesses ───────────────")
    witnesses_output = output_dir / "witnesses"
    serialize_witnesses(witnesses_df, witnesses_output)
    log.info("")

    # ── Étape 5 : OpenStemmata ────────────────────────────────
    # Intégration des stemmata dans les fichiers TEI text produits
    # à l'étape 3. Chaque fichier hid_{H-ID}.xml est enrichi avec
    # les éléments <listWit>, <textClass> et <text> récupérés
    # depuis le repo GitHub OpenStemmata.
    log.info("── Étape 5 : Intégration OpenStemmata ──────────────────")
    for tei_file in sorted(texts_output.glob("hid_*.xml")):
        fetch_and_integrate_from_df(
            texts_df=texts_df,
            target_tei_path=tei_file,
            output_path=tei_file,    # enrichissement en place
        )
    log.info("")

    # ── Résumé ────────────────────────────────────────────────
    n_texts     = len(list(texts_output.glob("hid_*.xml")))
    n_witnesses = len(list(witnesses_output.glob("hid_*.xml")))

    log.info("=" * 60)
    log.info("  Résumé")
    log.info("=" * 60)
    log.info(f"  Fichiers texts produits     : {n_texts}")
    log.info(f"  Fichiers witnesses produits : {n_witnesses}")
    log.info(f"  Dossier texts               : {texts_output}")
    log.info(f"  Dossier witnesses           : {witnesses_output}")
    log.info(f"  Log                         : {log_file.name}")
    log.info("=" * 60)


# ── Point d'entrée ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline heurist_to_tei : Heurist → fichiers TEI-P5.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--languages", "-l",
        nargs="+",
        default=["dum (Middle Dutch)", "enm (Middle English)"],
        help="Langues à traiter (défaut : dum et enm)",
    )
    parser.add_argument(
        "--output", "-o",
        default=Path("output"),
        type=Path,
        help="Dossier de sortie (défaut : ./output)",
    )
    args = parser.parse_args()
    run(args.languages, args.output)


if __name__ == "__main__":
    main()
