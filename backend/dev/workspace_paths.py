"""Repository-local paths; game workspaces are optional local configuration."""
from pathlib import Path
import os,sys
sys.dont_write_bytecode=True
DEV_ROOT=Path(__file__).resolve().parent
REPOSITORY_ROOT=DEV_ROOT.parents[1]
PROJECT_ROOT=Path(os.environ.get('NEOCORE_PROJECT_ROOT',str(REPOSITORY_ROOT)))
PACK_ROOT=DEV_ROOT.parent/'core'
SCRIPTS_ROOT=PACK_ROOT/'NeoForgeCoreScripts'
DELIVERY_ROOT=Path(os.environ.get('NEOCORE_DELIVERY_ROOT',str(REPOSITORY_ROOT/'outputs')))
