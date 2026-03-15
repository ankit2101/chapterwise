const BASE = '/api';

async function handleResponse(res) {
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error('Server did not respond correctly. Please try again or reduce the number of chapters.');
  }
  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`);
  }
  return data;
}

export async function getGrades(board) {
  const res = await fetch(`${BASE}/grades?board=${encodeURIComponent(board)}`);
  return handleResponse(res);
}

export async function getSubjects(board, grade) {
  const res = await fetch(`${BASE}/subjects?board=${encodeURIComponent(board)}&grade=${grade}`);
  return handleResponse(res);
}

export async function getChapters(board, grade, subject) {
  const res = await fetch(
    `${BASE}/chapters?board=${encodeURIComponent(board)}&grade=${grade}&subject=${encodeURIComponent(subject)}`
  );
  return handleResponse(res);
}

export async function startTest(chapterId, studentName = '', studentId = null) {
  const res = await fetch(`${BASE}/start-test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_id: chapterId, student_name: studentName, student_id: studentId }),
  });
  return handleResponse(res);
}

export async function submitAnswer(sessionKey, answerText, studentName = '') {
  const res = await fetch(`${BASE}/submit-answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_key: sessionKey,
      answer_text: answerText,
      student_name: studentName,
    }),
  });
  return handleResponse(res);
}

export async function getSession(sessionKey) {
  const res = await fetch(`${BASE}/session/${sessionKey}`);
  return handleResponse(res);
}

export async function studentLogin(name, pin) {
  const res = await fetch(`${BASE}/student/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, pin }),
  });
  return handleResponse(res);
}

export async function requestHint(sessionKey, answerText = '') {
  const res = await fetch(`${BASE}/student/hint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_key: sessionKey, answer_text: answerText }),
  });
  return handleResponse(res);
}

export async function getChapterSummary(chapterId) {
  const res = await fetch(`${BASE}/chapter-summary/${chapterId}`);
  return handleResponse(res);
}

export async function startCustomTest(chapterIds, studentName = '', studentId = null) {
  const res = await fetch(`${BASE}/start-custom-test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_ids: chapterIds, student_name: studentName, student_id: studentId }),
  });
  return handleResponse(res);
}

export async function prefetchQuestions(chapterIds) {
  const res = await fetch(`${BASE}/prefetch-questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_ids: chapterIds }),
  });
  return handleResponse(res);
}

export async function sessionPing(sessionKey) {
  const res = await fetch(`${BASE}/student/session-ping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_key: sessionKey }),
  });
  return handleResponse(res);
}
