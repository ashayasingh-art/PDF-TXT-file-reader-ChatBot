from flask import Flask, request, jsonify, render_template, send_from_directory
import os
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from nltk.tokenize import sent_tokenize
    _USE_NLTK = True
except Exception:
    _USE_NLTK = False

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'templates')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMPLATES_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024 * 1024
ALLOWED_EXT = {'pdf', 'txt'}

_state = {
    'current_file': None,
    'sentences': [],
    'vectorizer': None,
    'sentence_vectors': None
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def extract_text_from_pdf(path):
    text = ''
    with open(path, 'rb') as f:
        reader = PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'
    return text

def extract_text_from_txt(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def extract_text(path):
    ext = path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return extract_text_from_pdf(path)
    if ext == 'txt':
        return extract_text_from_txt(path)
    return ''

def split_sentences(text):
    if _USE_NLTK:
        try:
            return sent_tokenize(text, language='english')
        except Exception:
            pass
    import re
    parts = re.split(r'(?<=[\.\?\!])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]

def build_index_from_path(path):
    text = extract_text(path)
    sentences = split_sentences(text)
    if not sentences:
        return [], None, None
    vec = TfidfVectorizer()
    sentence_vectors = vec.fit_transform(sentences)
    return sentences, vec, sentence_vectors

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/files', methods=['GET'])
def list_files():
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if allowed_file(f)]
    return jsonify({'ok': True, 'files': files, 'current': _state['current_file']}), 200

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'ok': False, 'error': 'Unsupported file type. Allowed: pdf, txt'}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(save_path)
        print(f"[upload] saved: {save_path}")
    except Exception as e:
        print("[upload] save error:", e)
        return jsonify({'ok': False, 'error': f'Failed to save file: {str(e)}'}), 500

    try:
        sentences, vec, sentence_vectors = build_index_from_path(save_path)
        print(f"[upload] indexed sentences: {len(sentences)}")
    except Exception as e:
        print("[upload] indexing error:", e)
        return jsonify({'ok': False, 'error': f'Indexing error: {str(e)}'}), 500

    if not sentences:
        return jsonify({'ok': False, 'error': 'No text extracted from file.'}), 400

    _state.update({
        'current_file': filename,
        'sentences': sentences,
        'vectorizer': vec,
        'sentence_vectors': sentence_vectors
    })
    return jsonify({'ok': True, 'message': 'Uploaded and indexed', 'filename': filename, 'sentences': len(sentences)}), 200

@app.route('/select', methods=['POST'])
def select_file():
    data = request.get_json(silent=True)
    if not data or 'filename' not in data:
        return jsonify({'ok': False, 'error': 'No filename provided'}), 400
    filename = data['filename']
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(path):
        return jsonify({'ok': False, 'error': 'File not found'}), 404
    try:
        sentences, vec, sentence_vectors = build_index_from_path(path)
        print(f"[select] indexed sentences: {len(sentences)} for {filename}")
    except Exception as e:
        print("[select] indexing error:", e)
        return jsonify({'ok': False, 'error': f'Indexing error: {str(e)}'}), 500
    if not sentences:
        return jsonify({'ok': False, 'error': 'No text extracted from file.'}), 400

    _state.update({
        'current_file': filename,
        'sentences': sentences,
        'vectorizer': vec,
        'sentence_vectors': sentence_vectors
    })
    return jsonify({'ok': True, 'message': 'File selected and indexed', 'filename': filename, 'sentences': len(sentences)}), 200

@app.route('/ask', methods=['POST'])
def ask():
    if not _state['sentences']:
        return jsonify({'ok': False, 'error': 'No document loaded. Upload and index a file first.', 'answer': ''}), 400

    data = request.get_json(silent=True)
    if not data or 'question' not in data:
        return jsonify({'ok': False, 'error': 'No question provided', 'answer': ''}), 400

    question = data.get('question', '').strip()
    if not question:
        return jsonify({'ok': False, 'error': 'Empty question', 'answer': ''}), 400

    try:
        q_vec = _state['vectorizer'].transform([question])
        sims = cosine_similarity(q_vec, _state['sentence_vectors'])
        best_idx = int(sims.argmax())
        best_score = float(sims[0, best_idx])
        answer = _state['sentences'][best_idx]
        print(f"[ask] question: {question} -> idx {best_idx} score {best_score:.4f}")
        return jsonify({'ok': True, 'answer': answer, 'score': best_score}), 200
    except Exception as e:
        print("[ask] error:", e)
        return jsonify({'ok': False, 'error': f'Internal error: {str(e)}', 'answer': ''}), 500

@app.route('/status', methods=['GET'])
def status():
    loaded = bool(_state['sentences'])
    sentences_count = len(_state['sentences'])
    return jsonify({'ok': True, 'loaded': loaded, 'filename': _state['current_file'], 'sentences': sentences_count}), 200

@app.route('/_debug', methods=['GET'])
def _debug():
    return jsonify({
        'cwd': os.path.abspath('.'),
        'templates_folder': app.template_folder,
        'static_folder': app.static_folder,
        'index_exists': os.path.exists(os.path.join(app.template_folder or 'templates', 'index.html')),
        'css_exists': os.path.exists(os.path.join(app.static_folder or 'static', 'style.css')),
        'js_exists': os.path.exists(os.path.join(app.static_folder or 'static', 'static.js')),
        'uploads_list': os.listdir(app.config['UPLOAD_FOLDER']),
        'current_file': _state['current_file'],
        'sentence_count': len(_state['sentences'])
    })

if __name__ == '__main__':
    print("Starting Flask app from:", BASE_DIR)
    app.run(debug=True)