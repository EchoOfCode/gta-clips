import os

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_configuration_and_revisions():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini = os.path.join(backend_dir, "alembic.ini")
    assert os.path.exists(alembic_ini), "alembic.ini must exist in backend/"

    cfg = Config(alembic_ini)
    cfg.set_main_option("script_location", os.path.join(backend_dir, "migrations"))

    script_dir = ScriptDirectory.from_config(cfg)
    revisions = list(script_dir.walk_revisions())

    # Should have 0002_discovery and 0001_baseline
    rev_ids = [r.revision for r in revisions]
    assert "0002_discovery" in rev_ids
    assert "0001_baseline" in rev_ids

    # 0002_discovery must revise 0001_baseline
    discovery_rev = script_dir.get_revision("0002_discovery")
    assert discovery_rev.down_revision == "0001_baseline"

    # 0001_baseline is the root
    baseline_rev = script_dir.get_revision("0001_baseline")
    assert baseline_rev.down_revision is None
