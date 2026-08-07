type MessageHandler = (data: unknown) => void;
type StatusHandler = (status: 'connected' | 'disconnected' | 'error') => void;

/**
 * Future WebSocket client for real-time updates from FastAPI backend.
 *
 * Architecture placeholder — no functionality yet.
 *
 * Usage (future):
 *   const ws = WebSocketClient.getInstance();
 *   ws.connect();
 *   ws.subscribe('risk_update', handler);
 *   ws.disconnect();
 */
export class WebSocketClient {
  private static instance: WebSocketClient;
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<MessageHandler>>();
  private statusHandlers = new Set<StatusHandler>();

  static getInstance(): WebSocketClient {
    if (!WebSocketClient.instance) {
      WebSocketClient.instance = new WebSocketClient();
    }
    return WebSocketClient.instance;
  }

  connect(): void {
    // TODO: Implement when backend WebSocket is ready
    console.warn('[WebSocketClient] connect() — not yet implemented');
  }

  disconnect(): void {
    // TODO
    console.warn('[WebSocketClient] disconnect() — not yet implemented');
  }

  subscribe(_channel: string, _handler: MessageHandler): void {
    // TODO
    console.warn('[WebSocketClient] subscribe() — not yet implemented');
  }

  unsubscribe(_channel: string, _handler: MessageHandler): void {
    // TODO
    console.warn('[WebSocketClient] unsubscribe() — not yet implemented');
  }

  send(_data: unknown): void {
    // TODO
    console.warn('[WebSocketClient] send() — not yet implemented');
  }

  onStatus(_handler: StatusHandler): void {
    // TODO
    console.warn('[WebSocketClient] onStatus() — not yet implemented');
  }
}
