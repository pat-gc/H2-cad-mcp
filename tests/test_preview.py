import hashlib
import json
from pathlib import Path

import pytest

from h2cad.cli import main
from h2cad.preview import preview_fsgen

SOURCE = Path(__file__).resolve().parents[1] / "fixtures/robot/hollow_square_tube.fs"


def test_cli_preview_preserves_png_and_reports_actual_solids(tmp_path, capsys):
    from PIL import Image
    output = tmp_path / "tube.png"
    assert main(["preview", str(SOURCE), "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    with Image.open(output) as image:
        assert image.format == "PNG"
        image.verify()
    assert result == json.loads(output.with_suffix('.json').read_text())
    assert result['image_sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert result['geometry']['parts'] == 1
    assert result['geometry']['volume_mm3'] == pytest.approx(31680)
    assert result['kernel_valid_solids'] == 1
    assert result['remote'] == 'not_run' and result['native_compatibility'] == 'not_checked'


def test_failed_source_and_render_preserve_previous_preview(tmp_path, monkeypatch):
    from fsgen.native import local
    output = tmp_path / 'tube.png'
    report = output.with_suffix('.json')
    output.write_bytes(b'prior image'); report.write_bytes(b'prior report')
    bad = tmp_path / 'bad.fs'; bad.write_text('not a valid fsgen script')
    with pytest.raises(ValueError, match='trace failed'):
        preview_fsgen(bad, output)
    monkeypatch.setattr(local, 'render', lambda *args: None)
    with pytest.raises(ValueError, match='renderer'):
        preview_fsgen(SOURCE, output)
    assert output.read_bytes() == b'prior image' and report.read_bytes() == b'prior report'
    assert not list(tmp_path.glob('h2-preview-*'))


def test_preview_rejects_wrong_output_and_source_overwrite(tmp_path):
    with pytest.raises(ValueError, match='.png'):
        preview_fsgen(SOURCE, tmp_path / 'bad.jpg')
    same = tmp_path / 'source.png'
    with pytest.raises(ValueError, match='overwrite'):
        preview_fsgen(same, same)
