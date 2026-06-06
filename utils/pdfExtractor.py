from pypdf import PdfReader

pdf_path = "data-source/Bank-Policy.pdf"

def extract_text():
    reader = PdfReader(pdf_path)

    text = ""

    for page in reader.pages:
        text += page.extract_text() + "\n"

    return text