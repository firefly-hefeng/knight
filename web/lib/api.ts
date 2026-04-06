const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// 带重试和指数退避的 fetch
async function fetchWithRetry(
  url: string,
  options?: RequestInit,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const res = await fetch(url, {
        ...options,
        signal: AbortSignal.timeout(10000), // 10s timeout
      });
      if (res.ok) return res;

      // 4xx 不重试（客户端错误）
      if (res.status >= 400 && res.status < 500) {
        throw new Error(`Client error ${res.status}: ${res.statusText}`);
      }

      lastError = new Error(`Server error ${res.status}`);
    } catch (error) {
      lastError = error as Error;

      // AbortError（超时）或网络错误才重试
      if (error instanceof TypeError || (error as Error).name === 'AbortError') {
        // 继续重试
      } else if ((error as Error).message?.includes('Client error')) {
        throw error; // 4xx 不重试
      }
    }

    // 指数退避
    if (attempt < maxRetries - 1) {
      const delay = baseDelay * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error('Request failed after retries');
}

export async function createTask(name: string, description: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  return res.json();
}

export async function getTasks() {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks`, undefined, 2, 500);
  return res.json();
}

export async function getTask(taskId: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks/${taskId}`);
  return res.json();
}

export async function getTaskLogs(taskId: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks/${taskId}/logs`);
  return res.json();
}

export async function getAgents() {
  const res = await fetchWithRetry(`${API_BASE}/api/agents`, undefined, 2, 500);
  return res.json();
}

export async function getStats() {
  const res = await fetchWithRetry(`${API_BASE}/stats`);
  return res.json();
}

export async function getTaskDAG(taskId: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks/${taskId}/dag`);
  return res.json();
}

export async function getTaskAttempts(taskId: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks/${taskId}/attempts`);
  return res.json();
}

export async function submitFeedback(taskId: string, action: string, message?: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks/${taskId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, message: message || '' }),
  });
  return res.json();
}

export async function getFeedbackRequest(taskId: string) {
  const res = await fetchWithRetry(`${API_BASE}/api/tasks/${taskId}/feedback-request`);
  return res.json();
}
