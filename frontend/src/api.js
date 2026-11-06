const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message =
      typeof data.detail === "string"
        ? data.detail
        : "Something went wrong. Please try again.";

    throw new Error(message);
  }

  return data;
}

export function registerUser(userData) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify(userData),
  });
}

export function loginUser(credentials) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function getCurrentUser(token) {
  return request("/auth/me", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function getConversations(
  token,
  page = 1,
  pageSize = 20,
  status = null,
  priority = null,
  unassigned = null,
  assignedToId = null
) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (status) params.append("status", status);
  if (priority) params.append("priority", priority);
  if (unassigned) params.append("unassigned", "true");
  if (assignedToId) params.append("assigned_to_id", assignedToId);

  return request(`/conversations?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function createConversation(token, title) {
  return request("/conversations", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title }),
  });
}
export function getConversation(token, conversationId) {
  return request(`/conversations/${conversationId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function getConversationMessages(token, conversationId, page = 1, pageSize = 50) {
  return request(
    `/conversations/${conversationId}/messages?page=${page}&page_size=${pageSize}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
}

export function sendConversationMessage(token, conversationId, content) {
  return request(`/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  });
}

export function askAiAssistant(token, conversationId, content) {
  return request(`/conversations/${conversationId}/ask`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  });
}

export function updateConversation(token, conversationId, updates) {
  return request(`/conversations/${conversationId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(updates),
  });
}

export function assignConversation(token, conversationId, assignedToId) {
  return request(`/conversations/${conversationId}/assignment`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ assigned_to_id: assignedToId }),
  });
}

export function getAdminUsers(token, { role = null, isActive = null, page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (role) params.append("role", role);
  if (isActive !== null && isActive !== undefined) params.append("is_active", isActive);

  return request(`/admin/users?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function updateAdminUser(token, userId, updates) {
  return request(`/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(updates),
  });
}