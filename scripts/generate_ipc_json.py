# generate_ipc_json.py
import re
import json
from docx import Document

DOC_PATH = "The Indian Penal Code.docx"
OUTPUT_PATH = "ipc_clean.json"

SECTION_RE = re.compile(r"^(\d+[A-Z]?)\.\s*(.+)")
CHAPTER_RE = re.compile(r"^Chapter\s+([IVXLC]+)\s*(.*)", re.IGNORECASE)

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def split_explanations(text: str):
    parts = re.split(r"(Explanation\s*\.—)", text)
    main = parts[0].strip()
    explanations = []

    for i in range(1, len(parts), 2):
        explanations.append(clean(parts[i] + parts[i+1]))

    return main, explanations

def split_illustrations(text: str):
    parts = re.split(r"(Illustration[s]?\s*\.—?)", text)
    main = parts[0].strip()
    illustrations = []

    for i in range(1, len(parts), 2):
        illustrations.append(clean(parts[i] + parts[i+1]))

    return main, illustrations

def is_repealed(title: str, body: str) -> bool:
    combined = f"{title} {body}".lower()
    return "omitted" in combined or "repealed" in combined

def generate():
    doc = Document(DOC_PATH)

    sections = []
    current_chapter = None
    current_chapter_title = None
    current_section = None

    buffer = []

    for para in doc.paragraphs:
        text = clean(para.text)
        if not text:
            continue

        chap_match = CHAPTER_RE.match(text)
        if chap_match:
            current_chapter = f"Chapter {chap_match.group(1)}"
            current_chapter_title = chap_match.group(2)
            continue

        sec_match = SECTION_RE.match(text)
        if sec_match:
            # Save previous section
            if current_section and buffer:
                body = " ".join(buffer)
                body, explanations = split_explanations(body)
                body, illustrations = split_illustrations(body)

                if body and not is_repealed(current_section["title"], body):
                    current_section.update({
                        "text": body,
                        "explanations": explanations,
                        "illustrations": illustrations,
                    })
                    sections.append(current_section)

            # Start new section
            current_section = {
                "section_number": sec_match.group(1),
                "title": sec_match.group(2),
                "chapter": current_chapter,
                "chapter_title": current_chapter_title,
                "text": "",
                "explanations": [],
                "illustrations": [],
                "is_repealed": False,
                "source": "IPC 1860 (Amended upto 2018)"
            }
            buffer = []
            continue

        if current_section:
            buffer.append(text)

    # Flush last section
    if current_section and buffer:
        body = " ".join(buffer)
        body, explanations = split_explanations(body)
        body, illustrations = split_illustrations(body)

        if body and not is_repealed(current_section["title"], body):
            current_section.update({
                "text": body,
                "explanations": explanations,
                "illustrations": illustrations,
            })
            sections.append(current_section)

    print(f"✅ Extracted {len(sections)} valid IPC sections")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    generate()
