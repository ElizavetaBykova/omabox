// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);
ui.on_message('response', handleResponse);
ui.on_message('stream_end', handleStreamEnd);
ui.on_message('llm_error', handleLLMError);
ui.on_message('command_ok', handleCompletedCommand);
ui.on_message('command_error', handleCommandError);
ui.on_message('notification', handleNotification);
ui.on_message('notifications', handleNotificationList);

let thinkingMessageElement = null;
let lastUserPrompt = '';
let isFirstPrompt = true;
let thinkingMessageInterval = null;

const errorBanner = document.getElementById('error-banner');
const errorMessage = document.getElementById('error-message');
const chatMessagesContainer = document.getElementById('chat-messages-container');
const userInput = document.getElementById('user-input');
const messagesContainer = document.getElementById('messages');
const emptyChatContainer = document.getElementById('empty-chat-container');
const mainContent = document.querySelector('.main-content');
const sendButton = document.getElementById('send-button');
const sendButtonImg = sendButton ? sendButton.querySelector('img') : null;
const clearChatButton = document.getElementById('clear-chat-button-header');
const notificationItems = [];

function onUIConnected() {
  console.log('Connected to backend');
  hideError();
  setConnectionState('connected');
  ui.send_message('get_notifications', {}); // also shows notifications made before the page was opened
}

// ---------- LähiLab notifications ----------
const notificationsContainer = document.getElementById('notifications');
const noNotifications = document.getElementById('no-notifications');
const notificationCount = document.getElementById('notification-count');
const navNotificationCount = document.getElementById('nav-notification-count');

/** Builds one notification card. Uses textContent only (no HTML from the backend). */
function renderNotification(n) {
  const card = document.createElement('div');
  card.className = `notification light-${n.light}`;
  if (n.id !== undefined && n.id !== null) card.dataset.id = n.id;

  const meta = document.createElement('div');
  meta.className = 'notification-meta';
  const level = document.createElement('span');
  level.className = `badge level-${n.level}`;
  level.textContent = n.level + (n.pickup ? ' · pickup' : '');
  const source = document.createElement('span');
  source.className = `badge source-${n.source}`;
  source.textContent = n.pending ? 'template · LLM writing…' : (n.source === 'llm' ? `LLM ${n.secs}s` : 'template');
  const where = document.createElement('span');
  const temp = n.temp_c === null || n.temp_c === undefined ? '– °C' : `${n.temp_c} °C`;
  where.textContent = `${n.time} · ${n.box_id} · ${n.location} · ${n.kits} kits · ${temp} · ${n.scenario}`;
  meta.append(level, source, where);

  const text = document.createElement('div');
  text.textContent = n.message;
  card.append(meta, text);

  if (n.rejected) {
    const why = document.createElement('div');
    why.className = 'notification-rejected';
    why.textContent = `LLM text not used: ${n.rejected}`;
    card.appendChild(why);
  }
  return card;
}

function notificationLevelLabel(level) {
  const labels = {
    empty: 'Empty',
    ok: 'Within limits',
    soon: 'Collect today',
    urgent: 'Urgent pickup',
    overdue: 'Overdue',
  };
  return labels[level] || 'Review status';
}

function isBoxEvent(n) {
  return typeof n.scenario === 'string' && n.scenario.startsWith('event:');
}

function renderRecentItem(n) {
  const item = document.createElement('article');
  item.className = 'recent-item';

  const level = document.createElement('span');
  level.className = `mini-level level-${n.level || 'unknown'}`;
  level.textContent = n.level || 'update';

  const body = document.createElement('div');
  const message = document.createElement('p');
  message.textContent = n.message || 'Box status updated.';
  const meta = document.createElement('small');
  const details = [n.time, n.location, n.kits === null || n.kits === undefined ? null : `${n.kits} samples`]
    .filter(Boolean);
  meta.textContent = details.join(' · ');
  body.append(message, meta);
  item.append(level, body);
  return item;
}

function renderBoxCard(box) {
  const card = document.createElement('article');
  card.className = `box-overview-card edge-${box.light || 'off'}`;

  const header = document.createElement('div');
  header.className = 'box-overview-header';
  const identity = document.createElement('div');
  const title = document.createElement('h3');
  title.textContent = box.box_id;
  const location = document.createElement('p');
  location.textContent = box.location || 'Location not set';
  identity.append(title, location);

  const light = document.createElement('span');
  light.className = `light-badge light-${box.light || 'off'}`;
  light.textContent = box.light ? `${box.light} light` : 'No status';
  header.append(identity, light);

  const metrics = document.createElement('div');
  metrics.className = 'box-overview-metrics';
  const temperature = document.createElement('div');
  const temperatureLabel = document.createElement('span');
  temperatureLabel.textContent = 'Temperature';
  const temperatureValue = document.createElement('strong');
  temperatureValue.textContent = box.temp_c === null || box.temp_c === undefined
    ? '— °C' : `${box.temp_c} °C`;
  temperature.append(temperatureLabel, temperatureValue);

  const kits = document.createElement('div');
  const kitsLabel = document.createElement('span');
  kitsLabel.textContent = 'Samples inside';
  const kitsValue = document.createElement('strong');
  kitsValue.textContent = box.kits === null || box.kits === undefined ? '—' : box.kits;
  kits.append(kitsLabel, kitsValue);
  metrics.append(temperature, kits);

  const decision = document.createElement('div');
  decision.className = 'box-overview-decision';
  const level = document.createElement('span');
  level.className = `mini-level level-${box.level || 'unknown'}`;
  level.textContent = notificationLevelLabel(box.level);
  const pickup = document.createElement('strong');
  pickup.textContent = box.pickup ? 'Pickup required' : 'No pickup needed';
  decision.append(level, pickup);

  const update = document.createElement('p');
  update.className = 'box-overview-update';
  update.textContent = box.time ? `Last update · ${box.time}` : 'Last update received';

  card.append(header, metrics, decision, update);
  return card;
}

function refreshDashboard() {
  const boxesById = new Map();
  notificationItems.forEach(item => {
    if (isBoxEvent(item) && item.box_id && !boxesById.has(item.box_id)) {
      boxesById.set(item.box_id, item);
    }
  });
  const boxes = Array.from(boxesById.values());
  const boxCount = boxes.length;
  const sampleCount = boxes.reduce((total, box) =>
    total + (typeof box.kits === 'number' && Number.isFinite(box.kits) ? box.kits : 0), 0);
  const pickupCount = boxes.filter(box => box.pickup).length;
  const attentionCount = boxes.filter(box => box.light === 'red' || box.light === 'yellow').length;

  document.getElementById('dashboard-box-count').textContent = boxCount;
  document.getElementById('dashboard-kits').textContent = sampleCount;
  document.getElementById('dashboard-pickups').textContent = pickupCount;
  document.getElementById('dashboard-attention').textContent = attentionCount;
  document.getElementById('dashboard-box-grid-count').textContent = boxCount;

  const boxesGrid = document.getElementById('dashboard-boxes-grid');
  const boxesEmpty = document.getElementById('dashboard-boxes-empty');
  boxesGrid.replaceChildren(...boxes.map(renderBoxCard));
  boxesEmpty.style.display = boxCount ? 'none' : 'block';

  const recent = document.getElementById('dashboard-activity');
  const recentEmpty = document.getElementById('dashboard-activity-empty');
  const recentEvents = notificationItems.filter(isBoxEvent).slice(0, 4);
  recent.replaceChildren(...recentEvents.map(renderRecentItem));
  recentEmpty.style.display = recentEvents.length ? 'none' : 'block';
}

function renderNotificationList() {
  notificationsContainer.replaceChildren(...notificationItems.map(renderNotification));
  const count = notificationItems.length;
  notificationCount.textContent = count;
  navNotificationCount.textContent = count;
  noNotifications.style.display = count ? 'none' : 'block';
  refreshDashboard();
}

/** A new notification: newest on top. Same id = the LLM version of a card already shown: replace it. */
function handleNotification(n) {
  const index = n.id === undefined || n.id === null
    ? -1 : notificationItems.findIndex(item => String(item.id) === String(n.id));
  if (index >= 0) {
    notificationItems[index] = n;
  } else {
    notificationItems.unshift(n);
  }
  renderNotificationList();
}

/** The full list (oldest first) sent on connect. */
function handleNotificationList(list) {
  notificationItems.splice(0, notificationItems.length, ...(Array.isArray(list) ? [...list].reverse() : []));
  renderNotificationList();
}

function onUIDisconnected() {
  setConnectionState('disconnected');
  showError('Connection to backend lost. Please refresh the page or check the backend server.');
}

function setConnectionState(state) {
  const indicator = document.getElementById('connection-indicator');
  const label = document.getElementById('connection-label');
  const pill = document.getElementById('topbar-connection');
  const connected = state === 'connected';
  indicator.className = `connection-indicator is-${state}`;
  label.textContent = connected ? 'Connected to box' : state === 'connecting' ? 'Connecting…' : 'Box offline';
  pill.className = `connection-pill is-${state}`;
  pill.textContent = connected ? 'Connected' : state === 'connecting' ? 'Connecting' : 'Offline';
}

/**
 * Displays an error message in the error banner.
 * @param {string} message - The error message to display.
 */
function showError(message) {
  console.log(message);
  errorMessage.textContent = message;
  errorBanner.style.display = 'block';
}

/** Hides the error banner. */
function hideError() {
  errorBanner.style.display = 'none';
}

/** Scrolls the chat messages container to the bottom. */
function scrollToBottom() {
  chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

/** Removes the thinking/loading message from the chat if present. */
function removeThinkingMessage() {
  if (thinkingMessageInterval) {
    clearInterval(thinkingMessageInterval);
    thinkingMessageInterval = null;
  }
  if (thinkingMessageElement && thinkingMessageElement.parentNode) {
    thinkingMessageElement.parentNode.removeChild(thinkingMessageElement);
    thinkingMessageElement = null;
  }
}

/**
 * Handles a streamed response chunk from the backend.
 * On the first chunk, clears the thinking message and starts rendering the response.
 * Updates the AI response element with parsed markdown content.
 * @param {string} data - The text chunk received from the stream.
 */
function handleResponse(data) {
  const ai_msg = document.getElementById('active-ai-response');
  if (thinkingMessageElement) {
    if (thinkingMessageInterval) {
      clearInterval(thinkingMessageInterval);
      thinkingMessageInterval = null;
    }
    if (isFirstPrompt) {
      isFirstPrompt = false;
    }
    thinkingMessageElement.querySelector('.text-content').innerHTML = '';
    thinkingMessageElement.classList.remove('thinking-message');
    thinkingMessageElement.dataset.rawText = '';
    thinkingMessageElement = null;
  }

  if (ai_msg) {
    ai_msg.dataset.rawText += data;
    ai_msg.querySelector('.text-content').innerHTML = marked.parse(ai_msg.dataset.rawText);
    scrollToBottom();
  }
}

/**
 * Handles the end of a streamed response.
 * Removes the thinking message, restores UI to idle state, and updates button states.
 */
function handleStreamEnd() {
  removeThinkingMessage();
  const ai_msg = document.getElementById('active-ai-response');
  if (ai_msg) {
    ai_msg.id = '';
  }
  sendButton.classList.remove('sending-state');
  sendButtonImg.src = 'img/send.svg';
  updateSendButtonState();
  updateClearChatButtonState();
}

/** Handles the stop_stream command: ends the stream and restores the last user prompt. */
function handleStopStream() {
  handleStreamEnd();
  const disclaimer = document.createElement('div');
  disclaimer.className = 'stop-disclaimer';
  disclaimer.textContent = 'You stopped this response';
  messagesContainer.appendChild(disclaimer);

  userInput.value = lastUserPrompt;
  autoExpandInput(userInput);
  updateSendButtonState();
  userInput.focus();
}

/** Handles the clear_chat command: resets the chat UI to its initial empty state. */
function handleClearChat() {
  messagesContainer.innerHTML = '';
  emptyChatContainer.style.display = 'flex';
  mainContent.classList.remove('chat-active');
  userInput.value = '';
  userInput.style.height = '56px';
  lastUserPrompt = '';
  updateSendButtonState();
  updateClearChatButtonState();
  userInput.focus();
}

/**
 * Dispatches a completed command event to the appropriate handler.
 * @param {{command: string}} data - The command payload from the backend.
 */
function handleCompletedCommand(data) {
  console.log(`Command completed: ${data.command}`);

  if (data.command === 'stop_stream') {
    handleStopStream();
  } else if (data.command === 'clear_chat') {
    handleClearChat();
  }
}

/**
 * Handles a command error event from the backend.
 * @param {{command: string, error: string}} data - The error payload.
 */
function handleCommandError(data) {
  const message = `Command error: ${data.command} - ${data.error}`;
  showError(message);
}

/** Emits a clear_chat command to the backend. */
function sendClearChatCommand() {
  ui.send_message('commands', { command: 'clear_chat' });
}

/**
 * Handles an LLM error event from the backend.
 * Displays the error message, removes thinking state, and restores UI.
 * @param {{error: string}} data - The error payload containing the error message.
 */
function handleLLMError(data) {
  const message = `LLM error: ${data.error}`;
  showError(message);
  removeThinkingMessage();
  handleStreamEnd();
}

/**
 * Expands or collapses a textarea based on its content.
 * Maintains minimum height of 56px and maximum height of 200px.
 * Scrolls to the bottom when content expands beyond the minimum height.
 * @param {HTMLTextAreaElement} field - The textarea element to resize.
 */
function autoExpandInput(field) {
  field.style.height = '56px';

  if (field.value.trim() === '') {
    return;
  }

  const scrollHeight = field.scrollHeight;

  if (scrollHeight > 56) {
    const newHeight = Math.min(scrollHeight, 200);
    field.style.height = `${newHeight}px`;
    field.scrollTop = field.scrollHeight;
  }
}

/**
 * Updates the send button's disabled/enabled state.
 * Button is disabled when input is empty and enabled when the user is typing.
 * When a response is being streamed, the button acts as a stop button.
 */
function updateSendButtonState() {
  if (sendButton.classList.contains('sending-state')) {
    sendButton.classList.remove('disabled');
    sendButton.removeAttribute('disabled');
    return;
  }

  if (userInput.value.trim() === '') {
    sendButton.classList.add('disabled');
    sendButton.setAttribute('disabled', 'disabled');
  } else {
    sendButton.classList.remove('disabled');
    sendButton.removeAttribute('disabled');
  }
}

/** Updates the clear chat button's disabled/enabled state based on whether there are messages. */
function updateClearChatButtonState() {
  if (messagesContainer.children.length === 0) {
    clearChatButton.classList.add('disabled');
    clearChatButton.setAttribute('disabled', 'disabled');
  } else {
    clearChatButton.classList.remove('disabled');
    clearChatButton.removeAttribute('disabled');
  }
}

/**
 * Sends a user message to the backend and updates the chat UI.
 * Creates a user message element, displays a loading indicator,
 * and emits the message via WebSocket for backend processing.
 * @param {string} [text] - The message text. If omitted, reads from the textarea input.
 */
function sendMessage(text) {
  hideError();
  emptyChatContainer.style.display = 'none';
  mainContent.classList.add('chat-active');

  if (!text) {
    text = userInput.value;
  }
  lastUserPrompt = text;

  sendButton.classList.add('sending-state');
  sendButtonImg.src = 'img/stop.svg';

  userInput.value = '';
  userInput.style.height = '56px';
  updateSendButtonState();

  const userMessageDiv = document.createElement('div');
  userMessageDiv.className = 'user-message';
  userMessageDiv.textContent = text;
  messagesContainer.appendChild(userMessageDiv);
  scrollToBottom();

  thinkingMessageElement = document.createElement('div');
  thinkingMessageElement.className = 'ai-response thinking-message';
  thinkingMessageElement.id = 'active-ai-response';

  const icon = document.createElement('img');
  icon.src = 'img/sparkle.svg';
  icon.className = 'ai-icon';
  thinkingMessageElement.appendChild(icon);

  const textContent = document.createElement('div');
  textContent.className = 'text-content';

  const message = isFirstPrompt ? 'Loading Model' : 'Thinking';
  let dotsCount = 0;
  textContent.innerHTML = `<span class="circular-loader"></span>${message}`;
  thinkingMessageInterval = setInterval(() => {
    dotsCount = (dotsCount + 1) % 4;
    textContent.innerHTML = `<span class="circular-loader"></span>${message}${'.'.repeat(dotsCount)}`;
  }, 600);

  thinkingMessageElement.appendChild(textContent);

  messagesContainer.appendChild(thinkingMessageElement);
  scrollToBottom();

  ui.send_message('prompt', { prompt: text });
  updateClearChatButtonState();
  userInput.focus();
}

// Initial state
updateSendButtonState();
updateClearChatButtonState();
userInput.focus(); // Set initial focus

// Listen for input changes
userInput.addEventListener('input', () => {
  autoExpandInput(userInput);
  updateSendButtonState();
});

// Listen for Enter key press in the input field
userInput.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    // Ensure the send button is not disabled before sending
    if (!sendButton.classList.contains('disabled')) {
      sendMessage();
    }
  }
});

// Use a single click handler for the send button, acting as send or stop
sendButton.addEventListener('click', event => {
  event.preventDefault(); // Prevent default form submission if any
  if (sendButton.classList.contains('disabled')) {
    return;
  } else if (sendButton.classList.contains('sending-state')) {
    ui.send_message('commands', { command: 'stop_stream' });
  } else {
    sendMessage();
  }
});

clearChatButton.addEventListener('click', event => {
  if (clearChatButton.classList.contains('disabled')) {
    event.preventDefault(); // Prevent action if disabled
  } else {
    sendClearChatCommand();
  }
});

const pageTitles = {
  dashboard: 'Box overview',
  chat: 'Box assistant',
  activity: 'Notifications',
};

function showPage(pageName) {
  const title = pageTitles[pageName];
  if (!title) return;

  document.querySelectorAll('.page-view').forEach(page => {
    page.hidden = page.id !== `page-${pageName}`;
  });
  document.querySelectorAll('.nav-link').forEach(link => {
    const active = link.dataset.page === pageName;
    link.classList.toggle('is-active', active);
    if (active) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
  document.getElementById('page-title').textContent = title;
}

document.querySelectorAll('[data-page]').forEach(link => {
  link.addEventListener('click', event => {
    event.preventDefault();
    showPage(link.dataset.page);
  });
});

setConnectionState('connecting');
renderNotificationList();
