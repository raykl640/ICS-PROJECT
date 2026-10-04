"""Guard from conftest.py: default tests cannot overwrite the real chunks, indexes or feedback."""

from backend.app.config import DATA_DIR, Settings


def test_default_settings_in_tests_point_outside_the_real_data_dir() -> None:
    s = Settings()
    for path in (s.index_dir, s.dense_index_dir, s.sparse_index_dir, s.chunks_path, s.feedback_path, s.manifest_path):
        assert not path.resolve().is_relative_to(DATA_DIR.resolve()), path
    assert s.raw_pdf_dir == DATA_DIR / "raw_pdfs"  # inputs stay real (read-only)
