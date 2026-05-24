import sys
import types

import convert_documents


class FakeDocument:
    def export_to_markdown(self):
        return "# Converted\n\nPRJNA613586"

    def export_to_dict(self):
        return {"title": "Converted"}


class FakeConverter:
    def convert(self, path):
        return types.SimpleNamespace(document=FakeDocument())


def test_convert_with_docling_writes_markdown_and_json(tmp_path, monkeypatch):
    docling_module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = FakeConverter
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF fake")
    out = tmp_path / "converted"
    out.mkdir()

    result = convert_documents.convert_with_docling(source, out)

    assert result["status"] == "converted"
    assert (out / "paper.pdf.md").read_text(encoding="utf-8").startswith("# Converted")
    assert (out / "paper.pdf.docling.json").exists()


class FakeDataFrame:
    columns = ["sample", "run"]

    def __len__(self):
        return 1

    def to_csv(self, path, sep=",", index=False):
        path.write_text(f"sample{sep}run\nS1{sep}SRR1\n", encoding="utf-8")


def test_spreadsheet_preview_writes_tsv(tmp_path, monkeypatch):
    pandas_module = types.ModuleType("pandas")
    pandas_module.read_csv = lambda path, sep=",": FakeDataFrame()
    monkeypatch.setitem(sys.modules, "pandas", pandas_module)

    source = tmp_path / "supp.csv"
    source.write_text("sample,run\nS1,SRR1\n", encoding="utf-8")
    out = tmp_path / "converted"
    out.mkdir()

    previews = convert_documents.write_spreadsheet_previews(source, out)

    assert previews[0]["rows"] == 1
    assert (out / "supp.csv.preview.tsv").exists()
