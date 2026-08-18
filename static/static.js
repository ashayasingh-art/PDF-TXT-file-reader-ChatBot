// static/static.js
const statusEl = document.getElementById('status');
const answerEl = document.getElementById('answer');
const uploadForm = document.getElementById('uploadForm');
const fileInput = document.getElementById('fileInput');
const fileSelect = document.getElementById('fileSelect');
const uploadBtn = document.getElementById('uploadBtn');
const selectBtn = document.getElementById('selectBtn');
const refreshBtn = document.getElementById('refreshBtn');
const askBtn = document.getElementById('askBtn');
const questionInput = document.getElementById('question');

async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  try { return { res, data: JSON.parse(txt) }; }
  catch { return { res, data: null, text: txt }; }
}

async function refreshFiles() {
  const { data, res } = await fetchJson('/files');
  fileSelect.innerHTML = '';
  if (res.ok && data && data.files && data.files.length) {
    data.files.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f;
      fileSelect.appendChild(opt);
    });
    if (data.current) fileSelect.value = data.current;
  } else {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '-- no files uploaded --';
    fileSelect.appendChild(opt);
  }
  updateStatus();
}

async function updateStatus() {
  const { data, res } = await fetchJson('/status');
  if (res.ok && data && data.ok) {
    if (data.loaded) statusEl.textContent = `Loaded: ${data.filename} (${data.sentences} sentences)`;
    else statusEl.textContent = 'No document loaded.';
  } else statusEl.textContent = 'Status unavailable.';
}

uploadForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  if (!fileInput.files.length) { answerEl.textContent = 'Select a file to upload first.'; return; }
  uploadBtn.disabled = true;
  answerEl.textContent = 'Uploading and indexing...';
  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  try {
    const { res, data, text } = await fetchJson('/upload', { method: 'POST', body: fd });
    if (!res.ok) answerEl.textContent = 'Upload error: ' + (data && data.error ? data.error : (text || `Status ${res.status}`));
    else if (data && data.ok) { answerEl.textContent = 'Upload successful and indexed: ' + data.filename; await refreshFiles(); await updateStatus(); }
    else answerEl.textContent = 'Unexpected upload response.';
  } catch (err) { answerEl.textContent = 'Upload failed: ' + err; }
  finally { uploadBtn.disabled = false; }
});

selectBtn.addEventListener('click', async () => {
  const filename = fileSelect.value;
  if (!filename) { answerEl.textContent = 'Select a file from the list.'; return; }
  selectBtn.disabled = true;
  answerEl.textContent = 'Indexing selected file...';
  try {
    const { res, data, text } = await fetchJson('/select', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ filename })
    });
    if (!res.ok) answerEl.textContent = 'Select error: ' + (data && data.error ? data.error : (text || `Status ${res.status}`));
    else if (data && data.ok) { answerEl.textContent = `Selected and indexed: ${data.filename} (${data.sentences} sentences).`; await updateStatus(); }
    else answerEl.textContent = 'Unexpected select response.';
  } catch (err) { answerEl.textContent = 'Select failed: ' + err; }
  finally { selectBtn.disabled = false; }
});

refreshBtn.addEventListener('click', refreshFiles);

askBtn.addEventListener('click', async () => {
  const q = questionInput.value.trim();
  if (!q) { answerEl.textContent = 'Please type a question.'; return; }
  askBtn.disabled = true;
  answerEl.textContent = 'Thinking...';
  try {
    const { res, data, text } = await fetchJson('/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ question: q })
    });
    if (!res.ok) answerEl.textContent = 'Error: ' + (data && data.error ? data.error : (text || `Status ${res.status}`));
    else if (data && data.ok) answerEl.textContent = `Answer:\n${data.answer}\n\nScore: ${data.score !== undefined ? data.score.toFixed(3) : 'n/a'}`;
    else answerEl.textContent = 'Unexpected response from server.';
  } catch (err) { answerEl.textContent = 'Network error: ' + err; }
  finally { askBtn.disabled = false; }
});

// initial load
refreshFiles();
updateStatus();