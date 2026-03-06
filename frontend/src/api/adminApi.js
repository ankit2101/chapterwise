const BASE = '/api/admin';

async function parseJson(res) {
  try {
    return await res.json();
  } catch {
    if (res.status === 429) throw new Error('Too many requests — please wait a moment and try again.');
    if (res.status === 502 || res.status === 503) throw new Error('Server is temporarily unavailable. Please try again shortly.');
    throw new Error(`Server returned an unexpected response (${res.status}). Please try again.`);
  }
}

async function handleResponse(res) {
  const data = await parseJson(res);
  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`);
  }
  return data;
}

export async function getContent() {
  const res = await fetch(`${BASE}/content`, { credentials: 'include' });
  return handleResponse(res);
}

export async function uploadChapter(formData) {
  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  return handleResponse(res);
}

export async function deleteChapter(id) {
  const res = await fetch(`${BASE}/chapter/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  return handleResponse(res);
}

export async function regenerateQuestions(id) {
  const res = await fetch(`${BASE}/regenerate-questions/${id}`, {
    method: 'POST',
    credentials: 'include',
  });
  return handleResponse(res);
}

export async function changePassword(currentPassword, newPassword, confirmPassword) {
  const res = await fetch(`${BASE}/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  });
  return handleResponse(res);
}

export async function saveApiKey(apiKey) {
  const res = await fetch(`${BASE}/save-api-key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ api_key: apiKey }),
  });
  return handleResponse(res);
}

export async function getApiKeyStatus() {
  const res = await fetch(`${BASE}/api-key-status`, { credentials: 'include' });
  return handleResponse(res);
}

export async function getStudents() {
  const res = await fetch(`${BASE}/students`, { credentials: 'include' });
  return handleResponse(res);
}

export async function createStudent(name, pin) {
  const res = await fetch(`${BASE}/students`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name, pin }),
  });
  return handleResponse(res);
}

export async function deleteStudent(id) {
  const res = await fetch(`${BASE}/students/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  return handleResponse(res);
}

export async function getModelConfig() {
  const res = await fetch(`${BASE}/model-config`, { credentials: 'include' });
  return handleResponse(res);
}

export async function saveModel(modelId) {
  const res = await fetch(`${BASE}/save-model`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ model_id: modelId }),
  });
  return handleResponse(res);
}

export async function getStudentProgress() {
  const res = await fetch(`${BASE}/student-progress`, { credentials: 'include' });
  return handleResponse(res);
}

export async function bulkUploadChapters(formData) {
  const res = await fetch(`${BASE}/bulk-upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  // Bulk upload returns results even on partial failure — parse JSON regardless
  const data = await parseJson(res);
  if (!res.ok && !data.results) {
    throw new Error(data.error || 'Bulk upload failed');
  }
  return data;
}

export async function renameChapter(id, newName) {
  const res = await fetch(`${BASE}/chapter/${id}/rename`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ chapter_name: newName }),
  });
  return handleResponse(res);
}

export async function resetStudentPin(id, pin) {
  const res = await fetch(`${BASE}/students/${id}/reset-pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ pin }),
  });
  return handleResponse(res);
}
