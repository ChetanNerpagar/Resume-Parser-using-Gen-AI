# FLASK APP - Run the app using flask --app app.py run
import os, sys
from flask import Flask, request, render_template
from pypdf import PdfReader
from pypdf.errors import PdfStreamError

import json
from resumeparser import ats_extractor

sys.path.insert(0, os.path.abspath(os.getcwd()))


UPLOAD_PATH = r"__DATA__"
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route("/process", methods=["POST"])
def ats():
    results = {}
    errors = {}
    
    # Check if any files were uploaded
    files = request.files.getlist('pdf_doc')
    if not files or all(doc.filename == '' for doc in files):
        errors['_general'] = "No files were selected. Please select at least one PDF file."
        return render_template('index.html', data=results, errors=errors)
    
    for doc in files:
        if doc.filename == '':
            continue
        
        try:
            filepath = os.path.join(UPLOAD_PATH, doc.filename)
            doc.save(filepath)
            data = _read_file_from_path(filepath)
            
            if not data or data.strip() == '':
                errors[doc.filename] = "Failed to extract text from PDF file. The file may be corrupted or empty."
                continue
            
            extracted_data = ats_extractor(data)
            parsed_data = json.loads(extracted_data)
            
            # Check if the response contains an error
            if isinstance(parsed_data, dict) and 'error' in parsed_data:
                errors[doc.filename] = parsed_data.get('message', parsed_data.get('error', 'Unknown error occurred'))
            else:
                results[doc.filename] = parsed_data
        except json.JSONDecodeError as e:
            errors[doc.filename] = f"Failed to parse response: {str(e)}"
        except Exception as e:
            errors[doc.filename] = f"An error occurred while processing: {str(e)}"

    return render_template('index.html', data=results if results else None, errors=errors if errors else None)
 
def _read_file_from_path(path):
    """
    Read text from a PDF file using pypdf, handling corrupted/invalid PDFs gracefully.
    """
    try:
        # strict=False allows pypdf to be more tolerant of minor PDF errors
        reader = PdfReader(path, strict=False)
    except PdfStreamError:
        # Corrupted/invalid PDF stream
        return ""
    except Exception:
        # Any other unexpected issue while opening the PDF
        return ""

    data = ""
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        data += text

    return data


if __name__ == "__main__":
    app.run(port=5000, debug=True)

