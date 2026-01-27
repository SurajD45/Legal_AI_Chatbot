from docx import Document

doc = Document("The Indian Penal Code.docx")

for i, para in enumerate(doc.paragraphs[:50]):
    print(f"{i}: {para.text!r}")
