import { ref, onUnmounted } from "vue";

export type WebSocketState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export function useWebSocket(initialUrl?: string) {
  const socket = ref<WebSocket | null>(null);
  const state = ref<WebSocketState>("disconnected");
  const lastError = ref<string | null>(null);
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;
  const currentUrl = ref<string>(initialUrl || "");
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const messageHandlers = new Map<
    string,
    ((message: WebSocketMessage) => void)[]
  >();

  const connect = (url?: string) => {
    // Clear any pending reconnect timer
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    // Update URL if provided
    if (url) {
      // If URL changed and socket is open, close it to reconnect with new URL
      if (
        url !== currentUrl.value &&
        socket.value?.readyState === WebSocket.OPEN
      ) {
        socket.value.close();
      }
      currentUrl.value = url;
    }

    // Require a URL before connecting
    if (!currentUrl.value) {
      console.error("Cannot connect: no WebSocket URL provided");
      return;
    }

    // Prevent duplicate connections if already connecting or connected
    if (
      socket.value?.readyState === WebSocket.CONNECTING ||
      socket.value?.readyState === WebSocket.OPEN
    ) {
      console.log("WebSocket already connecting or connected");
      return;
    }

    state.value = "connecting";
    console.log("Connecting to WebSocket:", currentUrl.value);

    try {
      socket.value = new WebSocket(currentUrl.value);

      socket.value.onopen = () => {
        state.value = "connected";
        reconnectAttempts.value = 0;
        lastError.value = null;
        console.log("WebSocket connected");
      };

      socket.value.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log("WebSocket message received:", message);

          // Call registered handlers for this message type
          const handlers = messageHandlers.get(message.type);
          if (handlers) {
            handlers.forEach((handler) => handler(message));
          }

          // Also call wildcard handlers
          const wildcardHandlers = messageHandlers.get("*");
          if (wildcardHandlers) {
            wildcardHandlers.forEach((handler) => handler(message));
          }
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      socket.value.onerror = (error) => {
        console.error("WebSocket error:", error);
        state.value = "error";
        lastError.value = "WebSocket connection error";
      };

      socket.value.onclose = () => {
        console.log("WebSocket disconnected");
        state.value = "disconnected";
        socket.value = null;

        // Attempt to reconnect
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++;
          console.log(
            `Reconnecting in ${reconnectDelay}ms... (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`,
          );
          reconnectTimer = setTimeout(() => {
            connect();
          }, reconnectDelay);
        } else {
          console.error("Max reconnection attempts reached");
          lastError.value = "Failed to reconnect after multiple attempts";
        }
      };
    } catch (error) {
      console.error("Error creating WebSocket:", error);
      state.value = "error";
      lastError.value = "Failed to create WebSocket connection";
    }
  };

  const disconnect = () => {
    // Clear any pending reconnect timer
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    if (socket.value) {
      reconnectAttempts.value = maxReconnectAttempts; // Prevent auto-reconnect
      socket.value.close();
      socket.value = null;
    }
    state.value = "disconnected";
  };

  const send = (message: WebSocketMessage) => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(message));
      console.log("WebSocket message sent:", message);
    } else {
      console.error("WebSocket not connected, cannot send message");
      throw new Error("WebSocket not connected");
    }
  };

  const on = (
    messageType: string,
    handler: (message: WebSocketMessage) => void,
  ) => {
    if (!messageHandlers.has(messageType)) {
      messageHandlers.set(messageType, []);
    }
    messageHandlers.get(messageType)!.push(handler);
  };

  const off = (
    messageType: string,
    handler: (message: WebSocketMessage) => void,
  ) => {
    const handlers = messageHandlers.get(messageType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  };

  // Cleanup on unmount
  onUnmounted(() => {
    // Clear reconnect timer before disconnecting
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    disconnect();
    messageHandlers.clear();
  });

  return {
    // State
    state,
    lastError,
    reconnectAttempts,

    // Methods
    connect,
    disconnect,
    send,
    on,
    off,
  };
}

// Specific composable for chat WebSocket
export function useChatWebSocket(userId: string, dwellerId: string) {
  // Get WebSocket base URL from environment
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const wsUrl = `${protocol}//${host}/api/v1/ws/chat/${userId}/${dwellerId}`;
  const ws = useWebSocket(wsUrl);

  const sendTypingIndicator = (isTyping: boolean) => {
    ws.send({
      type: "typing",
      is_typing: isTyping,
    });
  };

  const sendMessage = (content: string) => {
    ws.send({
      type: "message",
      content,
    });
  };

  const ping = () => {
    ws.send({ type: "ping" });
  };

  return {
    ...ws,
    sendTypingIndicator,
    sendMessage,
    ping,
  };
}
