import { useCallback, useEffect, useState } from "react";
import {
  createConversation,
  getConversations,
  getCurrentUser,
  loginUser,
  registerUser,
  getConversation,
  getConversationMessages,
  sendConversationMessage,
  askAiAssistant,
  updateConversation,
  assignConversation,
  getAdminUsers,
  updateAdminUser,
} from "./api";
import "./App.css";

function App() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);

  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sendingReply, setSendingReply] = useState(false);
  const [askingAi, setAskingAi] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  const [conversations, setConversations] = useState([]);
  const [total, setTotal] = useState(0);
  const [title, setTitle] = useState("");
  const [activeAgents, setActiveAgents] = useState([]);
  const [adminTab, setAdminTab] = useState("tickets");
  const [adminUsers, setAdminUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [userRoleFilter, setUserRoleFilter] = useState("");

  const [loading, setLoading] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadConversations = useCallback(async (accessToken, filter = statusFilter) => {
    setLoadingConversations(true);
    setError("");

    try {
      const isUnassignedFilter = filter === "unassigned";
      const statusParam = isUnassignedFilter ? null : filter || null;
      const unassignedParam = isUnassignedFilter ? true : null;

      const data = await getConversations(
        accessToken,
        1,
        50,
        statusParam,
        null,
        unassignedParam
      );
      setConversations(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err.message || "Could not load conversations.");
    } finally {
      setLoadingConversations(false);
    }
  }, [statusFilter]);

  const loadAdminUsers = useCallback(async (accessToken, role = userRoleFilter) => {
    setLoadingUsers(true);
    setError("");

    try {
      const data = await getAdminUsers(accessToken, { role: role || null });
      setAdminUsers(data.items || []);
    } catch (err) {
      setError(err.message || "Failed to load users.");
    } finally {
      setLoadingUsers(false);
    }
  }, [userRoleFilter]);

  useEffect(() => {
    if (token) {
      loadConversations(token, statusFilter);
    }
  }, [token, statusFilter, loadConversations]);

  useEffect(() => {
    if (token && user?.role === "admin") {
      getAdminUsers(token, { role: "support", isActive: true })
        .then((data) => setActiveAgents(data.items || []))
        .catch((err) => console.error("Could not load active agents:", err));
    }
  }, [token, user]);

  useEffect(() => {
    if (token && user?.role === "admin" && adminTab === "users") {
      loadAdminUsers(token, userRoleFilter);
    }
  }, [token, user, adminTab, userRoleFilter, loadAdminUsers]);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      if (mode === "register") {
        await registerUser({
          email,
          password,
          full_name: fullName.trim() || null,
        });

        setMessage("Account created successfully. Please log in.");
        setMode("login");
        setPassword("");
      } else {
        const data = await loginUser({ email, password });
        const accessToken = data.access_token;
        const currentUser = await getCurrentUser(accessToken);

        setToken(accessToken);
        setUser(currentUser);
        setPassword("");
      }
    } catch (err) {
      setError(err.message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateConversation(event) {
    event.preventDefault();

    const trimmedTitle = title.trim();

    if (!trimmedTitle) {
      setError("Please enter a conversation title.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      await createConversation(token, trimmedTitle);
      setTitle("");
      setMessage("Conversation created successfully.");
      await loadConversations(token);
    } catch (err) {
      setError(err.message || "Could not create the conversation.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectConversation(conv) {
    setSelectedConversation(conv);
    setLoadingMessages(true);
    setError("");

    try {
      const [convDetails, msgData] = await Promise.all([
        getConversation(token, conv.id),
        getConversationMessages(token, conv.id, 1, 100),
      ]);
      setSelectedConversation(convDetails);
      setMessages(msgData.items || []);
    } catch (err) {
      setError(err.message || "Could not load conversation details.");
    } finally {
      setLoadingMessages(false);
    }
  }

  async function handleSendMessage(event) {
    event.preventDefault();
    const content = replyText.trim();
    if (!content || !selectedConversation) return;

    setError("");

    if (user.role === "customer") {
      setAskingAi(true);
      try {
        const result = await askAiAssistant(token, selectedConversation.id, content);
        setMessages((prev) => [...prev, result.question, result.answer]);
        setReplyText("");
      } catch (err) {
        setError(err.message || "Failed to send message.");
      } finally {
        setAskingAi(false);
      }
    } else {
      setSendingReply(true);
      try {
        const newMsg = await sendConversationMessage(token, selectedConversation.id, content);
        setMessages((prev) => [...prev, newMsg]);
        setReplyText("");
      } catch (err) {
        setError(err.message || "Could not send message.");
      } finally {
        setSendingReply(false);
      }
    }
  }

  async function handleUpdateStatus(newStatus) {
    if (!selectedConversation) return;
    setError("");

    try {
      const updated = await updateConversation(token, selectedConversation.id, {
        status: newStatus,
      });
      setSelectedConversation(updated);
      setConversations((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c))
      );
    } catch (err) {
      setError(err.message || "Could not update status.");
    }
  }

  async function handleUpdatePriority(newPriority) {
    if (!selectedConversation) return;
    setError("");

    try {
      const updated = await updateConversation(token, selectedConversation.id, {
        priority: newPriority,
      });
      setSelectedConversation(updated);
      setConversations((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c))
      );
    } catch (err) {
      setError(err.message || "Could not update priority.");
    }
  }

  async function handleAssignTicket(agentId) {
    if (!selectedConversation) return;
    setError("");

    try {
      const updated = await assignConversation(
        token,
        selectedConversation.id,
        agentId || null
      );
      setSelectedConversation(updated);
      setConversations((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c))
      );
    } catch (err) {
      setError(err.message || "Could not update ticket assignment.");
    }
  }

  async function handleUpdateRole(targetUser, newRole) {
    setError("");
    setMessage("");

    try {
      const updated = await updateAdminUser(token, targetUser.id, { role: newRole });
      setAdminUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setMessage(`Updated ${targetUser.email}'s role to ${newRole}.`);

      // Refresh active agents in case an agent was added or removed
      const agentData = await getAdminUsers(token, { role: "support", isActive: true });
      setActiveAgents(agentData.items || []);
    } catch (err) {
      setError(err.message || "Could not update user role.");
    }
  }

  async function handleToggleActive(targetUser) {
    setError("");
    setMessage("");

    try {
      const updated = await updateAdminUser(token, targetUser.id, {
        is_active: !targetUser.is_active,
      });
      setAdminUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setMessage(
        `${targetUser.email} is now ${updated.is_active ? "active" : "inactive"}.`
      );

      // Refresh active agents list
      const agentData = await getAdminUsers(token, { role: "support", isActive: true });
      setActiveAgents(agentData.items || []);
    } catch (err) {
      setError(err.message || "Could not toggle user status.");
    }
  }

  function handleBackToList() {
    setSelectedConversation(null);
    setMessages([]);
    setReplyText("");
    setError("");
  }

  function handleLogout() {
    setToken(null);
    setUser(null);
    setConversations([]);
    setSelectedConversation(null);
    setMessages([]);
    setReplyText("");
    setStatusFilter("");
    setActiveAgents([]);
    setAdminTab("tickets");
    setAdminUsers([]);
    setUserRoleFilter("");
    setTotal(0);
    setEmail("");
    setPassword("");
    setFullName("");
    setTitle("");
    setError("");
    setMessage("");
    setMode("login");
  }

  // Authenticated dashboard
  if (token && user) {
    return (
      <main className="page">
        <section className={`dashboard ${selectedConversation ? "wide" : ""}`}>
          <header className="dashboard-header">
            <div>
              <div className="brand-mark">AI</div>
              <p className="eyebrow">AI SUPPORT PLATFORM</p>
              <h1>
                Welcome{user.full_name ? `, ${user.full_name}` : ""}
              </h1>
              <p className="subtitle">
                Manage your support conversations.
              </p>
            </div>

            <button
              className="button button-secondary"
              type="button"
              onClick={handleLogout}
            >
              Log out
            </button>
          </header>

          <section className="profile-panel">
            <h2>Your account</h2>

            <div className="profile-grid">
              <div>
                <span className="field-label">Email</span>
                <p>{user.email}</p>
              </div>

              <div>
                <span className="field-label">Role</span>
                <p>{user.role}</p>
              </div>

              <div>
                <span className="field-label">Account status</span>
                <p>{user.is_active ? "Active" : "Inactive"}</p>
              </div>
            </div>
          </section>

          {user.role === "admin" && (
            <nav className="admin-nav">
              <button
                type="button"
                className={`admin-nav-btn ${adminTab === "tickets" ? "active" : ""}`}
                onClick={() => {
                  setAdminTab("tickets");
                  setSelectedConversation(null);
                }}
              >
                🎫 Ticket Queue
              </button>
              <button
                type="button"
                className={`admin-nav-btn ${adminTab === "users" ? "active" : ""}`}
                onClick={() => setAdminTab("users")}
              >
                👥 User & Agent Management
              </button>
            </nav>
          )}

          {adminTab === "users" && user.role === "admin" ? (
            <section className="conversation-panel">
              <div className="section-heading">
                <div>
                  <h2>User & Agent Management</h2>
                  <p className="subtitle">
                    View registered users, assign roles, and manage active support staff.
                  </p>
                </div>

                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => loadAdminUsers(token, userRoleFilter)}
                  disabled={loadingUsers}
                >
                  {loadingUsers ? "Refreshing..." : "Refresh"}
                </button>
              </div>

              {/* Role Filter Tabs */}
              <div className="filter-tabs">
                {[
                  { label: "All Roles", value: "" },
                  { label: "Support Agents", value: "support" },
                  { label: "Customers", value: "customer" },
                  { label: "Admins", value: "admin" },
                ].map((tab) => (
                  <button
                    key={tab.value}
                    type="button"
                    className={`filter-tab ${userRoleFilter === tab.value ? "active" : ""}`}
                    onClick={() => setUserRoleFilter(tab.value)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {error && <div className="alert error">{error}</div>}
              {message && <div className="success">{message}</div>}

              {loadingUsers ? (
                <p className="empty-state">Loading users...</p>
              ) : adminUsers.length === 0 ? (
                <div className="empty-state">
                  <h3>No users found</h3>
                  <p>There are no users matching the selected role filter.</p>
                </div>
              ) : (
                <div className="users-table-wrapper">
                  <table className="users-table">
                    <thead>
                      <tr>
                        <th>User</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adminUsers.map((u) => (
                        <tr key={u.id}>
                          <td>
                            <div style={{ fontWeight: 600 }}>
                              {u.full_name || "(No name)"}
                              {u.id === user.id ? " (You)" : ""}
                            </div>
                            <div style={{ fontSize: "12px", color: "#64748b" }}>
                              {u.email}
                            </div>
                          </td>
                          <td>
                            <select
                              className="agent-select"
                              value={u.role}
                              disabled={u.id === user.id}
                              onChange={(e) => handleUpdateRole(u, e.target.value)}
                              title={
                                u.id === user.id
                                  ? "Cannot change your own role"
                                  : "Change role"
                              }
                            >
                              <option value="customer">Customer</option>
                              <option value="support">Support Agent</option>
                              <option value="admin">Admin</option>
                            </select>
                          </td>
                          <td>
                            <span
                              className={`status ${
                                u.is_active ? "status-resolved" : "status-closed"
                              }`}
                            >
                              {u.is_active ? "Active" : "Inactive"}
                            </span>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="button button-secondary"
                              style={{ padding: "6px 12px", fontSize: "12px" }}
                              disabled={u.id === user.id}
                              onClick={() => handleToggleActive(u)}
                              title={
                                u.id === user.id
                                  ? "Cannot deactivate your own account"
                                  : ""
                              }
                            >
                              {u.is_active ? "Deactivate" : "Activate"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : (
            <section className="conversation-panel">
            {selectedConversation ? (
              /* --- CONVERSATION DETAIL VIEW --- */
              <div className="detail-view">
                <button
                  className="back-link"
                  type="button"
                  onClick={handleBackToList}
                >
                  ← Back to conversations
                </button>

                <div className="detail-header">
                  <div className="detail-title-row">
                    <h2>{selectedConversation.title}</h2>
                    <span className={`status status-${selectedConversation.status}`}>
                      {selectedConversation.status.replaceAll("_", " ")}
                    </span>
                  </div>

                  <div className="conversation-meta">
                    <span>Priority: <strong>{selectedConversation.priority}</strong></span>
                    <span>Ticket ID: {selectedConversation.id}</span>
                    {selectedConversation.created_at && (
                      <span>Created: {new Date(selectedConversation.created_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>

                {/* --- SUPPORT AGENT CONTROLS --- */}
                {(user.role === "support" || user.role === "admin") && (
                  <div className="agent-controls">
                    <span className="agent-controls-label">Agent Actions:</span>
                    <div>
                      <label htmlFor="change-status" style={{ fontSize: "12px", marginRight: "6px" }}>Status:</label>
                      <select
                        id="change-status"
                        className="agent-select"
                        value={selectedConversation.status}
                        onChange={(e) => handleUpdateStatus(e.target.value)}
                      >
                        <option value="open">Open</option>
                        <option value="in_progress">In Progress</option>
                        <option value="waiting_on_customer">Waiting on Customer</option>
                        <option value="resolved">Resolved</option>
                        <option value="closed">Closed</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="change-priority" style={{ fontSize: "12px", marginRight: "6px" }}>Priority:</label>
                      <select
                        id="change-priority"
                        className="agent-select"
                        value={selectedConversation.priority}
                        onChange={(e) => handleUpdatePriority(e.target.value)}
                      >
                        <option value="low">Low</option>
                        <option value="normal">Normal</option>
                        <option value="high">High</option>
                        <option value="urgent">Urgent</option>
                      </select>
                    </div>

                    {user.role === "admin" && (
                      <div>
                        <label htmlFor="assign-agent" style={{ fontSize: "12px", marginRight: "6px" }}>Assign Agent:</label>
                        <select
                          id="assign-agent"
                          className="agent-select"
                          value={selectedConversation.assigned_to_id || ""}
                          onChange={(e) => handleAssignTicket(e.target.value)}
                        >
                          <option value="">(Unassigned)</option>
                          {activeAgents.map((agent) => (
                            <option key={agent.id} value={agent.id}>
                              {agent.full_name ? `${agent.full_name} (${agent.email})` : agent.email}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                )}

                {error && <div className="alert error">{error}</div>}

                {/* --- MESSAGE THREAD --- */}
                <div className="messages-container">
                  {loadingMessages ? (
                    <p className="empty-state">Loading messages...</p>
                  ) : messages.length === 0 ? (
                    <p className="empty-state">No messages in this conversation yet. Send the first message below.</p>
                  ) : (
                    messages.map((msg) => {
                      const isAssistant = msg.role === "assistant";
                      const isSupport = msg.role === "support";
                      const roleClass = isAssistant
                        ? "message-assistant"
                        : isSupport
                        ? "message-support"
                        : "message-customer";

                      const roleLabel = isAssistant
                        ? "✨ AI Assistant"
                        : isSupport
                        ? "🎧 Support Agent"
                        : "👤 Customer";

                      return (
                        <article key={msg.id} className={`message-bubble ${roleClass}`}>
                          <div className="message-header">
                            <span>{roleLabel}</span>
                            <span>
                              {new Date(msg.created_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>
                          <p className="message-text">{msg.content}</p>
                        </article>
                      );
                    })
                  )}
                  {askingAi && (
                    <div className="ai-thinking-bubble">
                      ✨ AI Assistant is searching documentation and drafting an answer...
                    </div>
                  )}
                </div>

                {/* --- REPLY COMPOSER --- */}
                <form className="composer" onSubmit={handleSendMessage}>
                  <textarea
                    rows={3}
                    placeholder="Type your message..."
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    required
                  />
                  <div className="composer-actions">
                    <button
                      className="button button-primary"
                      type="submit"
                      disabled={sendingReply || askingAi}
                    >
                      {askingAi || sendingReply ? "Sending..." : "Send Message"}
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              /* --- CONVERSATIONS LIST & FILTERS --- */
              <>
                <div className="section-heading">
                  <div>
                    <h2>Conversations</h2>
                    <p className="subtitle">
                      {total} conversation{total === 1 ? "" : "s"} found
                    </p>
                  </div>

                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => loadConversations(token, statusFilter)}
                    disabled={loadingConversations}
                  >
                    {loadingConversations ? "Refreshing..." : "Refresh"}
                  </button>
                </div>

                {/* Status Filter Tabs */}
                <div className="filter-tabs">
                  {[
                    { label: "All", value: "" },
                    ...(user.role === "admin"
                      ? [{ label: "⚡ Unassigned", value: "unassigned" }]
                      : []),
                    { label: "Open", value: "open" },
                    { label: "In Progress", value: "in_progress" },
                    { label: "Waiting", value: "waiting_on_customer" },
                    { label: "Resolved", value: "resolved" },
                    { label: "Closed", value: "closed" },
                  ].map((tab) => (
                    <button
                      key={tab.value}
                      type="button"
                      className={`filter-tab ${statusFilter === tab.value ? "active" : ""}`}
                      onClick={() => setStatusFilter(tab.value)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Create Conversation Form */}
                <form className="create-form" onSubmit={handleCreateConversation}>
                  <label htmlFor="conversation-title">New conversation title</label>
                  <div className="create-form-row">
                    <input
                      id="conversation-title"
                      type="text"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="e.g. Help with my account"
                      maxLength={255}
                      required
                    />
                    <button
                      className="button button-primary"
                      type="submit"
                      disabled={loading}
                    >
                      {loading ? "Creating..." : "Create"}
                    </button>
                  </div>
                </form>

                {error && <div className="alert error">{error}</div>}
                {message && <div className="success">{message}</div>}

                {loadingConversations ? (
                  <p className="empty-state">Loading conversations...</p>
                ) : conversations.length === 0 ? (
                  <div className="empty-state">
                    <h3>No conversations found</h3>
                    <p>There are no conversations matching the current filter.</p>
                  </div>
                ) : (
                  <div className="conversation-list">
                    {conversations.map((conversation) => (
                      <article
                        className="conversation-card clickable"
                        key={conversation.id}
                        onClick={() => handleSelectConversation(conversation)}
                      >
                        <div className="conversation-card-heading">
                          <h3>{conversation.title}</h3>
                          <span className={`status status-${conversation.status}`}>
                            {conversation.status.replaceAll("_", " ")}
                          </span>
                        </div>

                        <div className="conversation-meta">
                          <span>Priority: {conversation.priority}</span>
                          <span>ID: {conversation.id}</span>
                          {(user.role === "admin" || user.role === "support") && (
                            conversation.assigned_to_id ? (
                              <span>
                                👤 Agent:{" "}
                                {activeAgents.find((a) => a.id === conversation.assigned_to_id)?.full_name ||
                                  activeAgents.find((a) => a.id === conversation.assigned_to_id)?.email ||
                                  "Assigned"}
                              </span>
                            ) : (
                              <span style={{ color: "#d97706", fontWeight: 600 }}>
                                ⚠️ Unassigned
                              </span>
                            )
                          )}
                          <span>Click to open thread →</span>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </>
            )}
          </section>
        )}
      </section>
    </main>
    );
  }

  // Login and registration: retain the original CSS class names
  return (
    <main className="page">
      <section className="card">
        <div className="brand-mark">AI</div>

        <p className="eyebrow">AI SUPPORT PLATFORM</p>

        <h1>
          {mode === "login" ? "Welcome back" : "Create your account"}
        </h1>

        <p className="subtitle">
          {mode === "login"
            ? "Sign in to manage your support conversations."
            : "Register to get started."}
        </p>

        <div className="mode-switch">
          <button
            type="button"
            className={mode === "login" ? "mode active" : "mode"}
            onClick={() => {
              setMode("login");
              setError("");
              setMessage("");
            }}
          >
            Log in
          </button>

          <button
            type="button"
            className={mode === "register" ? "mode active" : "mode"}
            onClick={() => {
              setMode("register");
              setError("");
              setMessage("");
            }}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <div className="form-group">
              <label htmlFor="full-name">Full name (optional)</label>
              <input
                id="full-name"
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Your name"
                maxLength={255}
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              minLength={mode === "register" ? 8 : undefined}
              maxLength={128}
              required
            />
          </div>

          {error && <div className="alert error">{error}</div>}
          {message && <div className="success">{message}</div>}

          <button
            className="primary-button"
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Log in"
                : "Create account"}
          </button>
        </form>

        <p className="footer-note">
          Secure access to your AI support workspace.
        </p>
      </section>
    </main>
  );
}

export default App;