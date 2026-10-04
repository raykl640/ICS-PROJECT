// Minimal EventSource stand-in: tests push named events (server) or fail() the connection (network).
export class MockEventSource extends EventTarget {
  static instances: MockEventSource[] = [];
  readonly url: string;
  closed = false;

  constructor(url: string) {
    super();
    this.url = url;
    MockEventSource.instances.push(this);
  }

  static get last(): MockEventSource {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }

  static reset(): void {
    MockEventSource.instances = [];
  }

  /** A named server event with a JSON payload. */
  emit(name: string, data: unknown): void {
    this.dispatchEvent(new MessageEvent(name, { data: JSON.stringify(data) }));
  }

  /** The connection dropping (a bare "error" Event, no data). */
  fail(): void {
    this.dispatchEvent(new Event("error"));
  }

  close(): void {
    this.closed = true;
  }
}
